# -*- coding: utf-8 -*-
"""
GK Studio V3 - Web Research Agent

Gemini Google Search grounding ile URL vermeden web arastirmasi yapar.
Bulunan kaynaklari Gemini URL Context ile ikinci asamada derinlestirir.
Sonucu yerel Qwen'e aktarilabilecek temiz bir arastirma paketi olarak uretir.

Harici DuckDuckGo / Firecrawl bagimliligi yoktur.
Yalnizca Python standart kutuphanesi kullanilir.
"""

import json
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse

from config import GEMINI_API_KEY
from web_guard import apply_web_guard


GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_GENERATE_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)

MAX_SEARCH_SOURCE_URLS = 8
MAX_SESSION_CONTEXT_CHARS = 6000
MAX_SEARCH_TEXT_CHARS = 12000
MAX_DEEP_TEXT_CHARS = 16000
MAX_FINAL_REPORT_CHARS = 30000
REQUEST_TIMEOUT = 60
SOURCE_RESOLVE_TIMEOUT = 8


def _resolve_source_url(url):
    """Google grounding redirect URL'sini mumkunse asil hedef URL'ye cevirir."""
    url = str(url or "").strip()
    if not url:
        return ""

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return url

        if not parsed.netloc.lower().endswith("vertexaisearch.cloud.google.com"):
            return url

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "GK-Studio-V3-WebResearch/1.0"},
            method="GET",
        )

        with urllib.request.urlopen(req, timeout=SOURCE_RESOLVE_TIMEOUT) as resp:
            final_url = resp.geturl() or url
            return str(final_url).strip()
    except Exception:
        return url


def _normalize_sources(sources):
    """Kaynak listesindeki grounding redirect URL'lerini normalize eder."""
    normalized = []
    seen = set()

    for src in sources or []:
        if not isinstance(src, dict):
            continue

        raw_url = str(src.get("url") or "").strip()
        if not raw_url:
            continue

        final_url = _resolve_source_url(raw_url)
        key = final_url.lower()

        if key in seen:
            continue

        seen.add(key)
        normalized.append({
            "title": str(src.get("title") or "").strip(),
            "url": final_url,
            "grounding_url": raw_url if raw_url != final_url else "",
        })

    return normalized


def _clip(text, limit):
    text = str(text or "")
    if len(text) <= limit:
        return text
    cut = text.rfind("\n", 0, limit)
    if cut < limit // 2:
        cut = limit
    return text[:cut] + "\n[... devamı kırpıldı ...]"


def _unique(items):
    out = []
    seen = set()
    for item in items:
        item = str(item or "").strip()
        if not item:
            continue
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _extract_urls(text):
    if not text:
        return []
    found = re.findall(r"https?://[^\s<>\"']+", str(text))
    clean = []
    for url in found:
        url = url.rstrip(".,);]}>")
        try:
            parsed = urlparse(url)
            if parsed.scheme in ("http", "https") and parsed.netloc:
                clean.append(url)
        except Exception:
            continue
    return _unique(clean)


def _gemini_request(prompt, tools):
    if not GEMINI_API_KEY:
        return {
            "ok": False,
            "error": "GEMINI_API_KEY eksik veya .env dosyasından okunamadı."
        }

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": tools,
        "generationConfig": {"temperature": 0.1}
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        GEMINI_GENERATE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_API_KEY
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "data": json.loads(raw)}
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode("utf-8", errors="replace")
        except Exception:
            detail = str(e)
        return {
            "ok": False,
            "error": f"Gemini HTTP {e.code}: {_clip(detail, 1200)}"
        }
    except Exception as e:
        return {"ok": False, "error": f"Gemini bağlantı hatası: {e}"}


def _extract_candidate(data):
    candidates = (data or {}).get("candidates") or []
    return candidates[0] if candidates else {}


def _extract_text(data):
    candidate = _extract_candidate(data)
    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    texts = []
    for part in parts:
        if isinstance(part, dict) and part.get("text"):
            texts.append(str(part["text"]))

    return "".join(texts).strip()


def _extract_search_metadata(data):
    candidate = _extract_candidate(data)
    metadata = (
        candidate.get("groundingMetadata")
        or candidate.get("grounding_metadata")
        or {}
    )

    queries = (
        metadata.get("webSearchQueries")
        or metadata.get("web_search_queries")
        or []
    )

    sources = []
    chunks = (
        metadata.get("groundingChunks")
        or metadata.get("grounding_chunks")
        or []
    )

    for chunk in chunks:
        if not isinstance(chunk, dict):
            continue
        web = chunk.get("web") or {}
        if not isinstance(web, dict):
            continue
        uri = web.get("uri") or web.get("url")
        title = web.get("title") or ""
        if uri:
            sources.append({"title": str(title).strip(), "url": str(uri).strip()})

    content = candidate.get("content") or {}
    for part in content.get("parts") or []:
        if not isinstance(part, dict):
            continue
        for ann in part.get("annotations") or []:
            if not isinstance(ann, dict):
                continue
            if ann.get("type") == "url_citation" and ann.get("url"):
                sources.append({
                    "title": str(ann.get("title") or "").strip(),
                    "url": str(ann["url"]).strip()
                })

    unique_sources = []
    seen = set()
    for src in sources:
        url = src["url"]
        if url.lower() in seen:
            continue
        seen.add(url.lower())
        unique_sources.append(src)

    return {"queries": _unique(queries), "sources": unique_sources}


def _format_sources(sources):
    if not sources:
        return "Kaynak URL metadata içinde alınamadı."

    lines = []
    for idx, src in enumerate(sources, 1):
        lines.append(
            f"{idx}. {src.get('title') or 'Baslıksız kaynak'}\n"
            f"   {src.get('url') or ''}"
        )
    return "\n".join(lines)


def _build_search_prompt(user_prompt, target_url="", session_context=""):
    target_note = ""
    if target_url:
        target_note = (
            f"\n\nKULLANICI HEDEF URL: {target_url}\n"
            "Bu URL'yi arastirmanin ana hedeflerinden biri olarak ele al."
        )

    previous_note = ""
    if session_context:
        previous_note = (
            "\n\nONCEKI WEB OTURUMU BAGLAMI:\n"
            f"{_clip(session_context, MAX_SESSION_CONTEXT_CHARS)}"
        )

    return f"""
GK Studio V3 icin calisan bir WEB ARASTIRMA AJANISIN.
Kullanici sorusunu once internette arastir; sadece model hafizasina dayanma.

KULLANICI SORUSU:
{user_prompt}

ARASTIRMA KURALLARI:
1. Soruyu gerekli alt aramalara ayir ve Google Search grounding kullan.
2. Guncel ve resmi kaynaklara oncelik ver; gerekirse birden fazla bagimsiz kaynak kullan.
3. Belirtilen donem, ulke, birim ve para birimini kontrol et.
4. Ayni verinin tekrarlarini dikkate alma.
5. Kaynakta bulunmayan sayilari, ciroyu veya tarihleri uydurma.
6. Veri yoksa acikca bulunamadigini belirt.
7. Kaynaklar celisiyorsa celiskiyi ve kaynaklari ayri belirt.
8. Site arastirmasinda resmi site, urun sayfalari, katalog/PDF ve iletisim sayfalarina oncelik ver.
9. Kullanici tablo veya Excel istiyorsa verileri satir-sutun mantiginda temiz ve dogrulanabilir sekilde cikart.
10. Buldugun kaynak URL'lerini koru.
11. Bir veri listesi için kullanilabilir kanit sayisi yetersizse listeyi doldurmak icin tahmin yapma.
12. Kullanici "ilk N" veya "top N" isterse N sayisina ulasamiyorsan eksik kayitlari acikca belirt.
{target_note}
{previous_note}
""".strip()


def _build_deep_prompt(user_prompt, search_text, urls, target_url=""):
    url_lines = "\n".join(f"- {u}" for u in urls)
    target_note = f"\nONCELIKLI HEDEF URL: {target_url}\n" if target_url else ""

    return f"""
GK Studio V3 WEB ARASTIRMA AJANISIN.
Asagidaki URL'lerin gercek icerigini URL Context ile incele.

KULLANICI SORUSU:
{user_prompt}

ILK WEB ARAMASI BULGULARI:
{_clip(search_text, MAX_SEARCH_TEXT_CHARS)}

INCELEME URL'LERI:
{url_lines}
{target_note}

KURALLAR:
1. Erisilebilen gercek icerige dayan.
2. Tarih, adet, fiyat, ciro, ulke ve marka gibi alanlari acikca ayir.
3. Bilgi URL'de yoksa tahmin etme.
4. Celiskileri saklama.
5. Site incelemesinde sayfa basliklari, urun/kategori yapisi, iletisim, katalog/PDF ve onemli baglantilari ayir.
6. Sayisal veri isteniyorsa temiz tablo satirlari uret.
7. Hangi URL'den hangi bilginin alindigini belirt.
""".strip()


class WebResearchAgent:
    @classmethod
    def research(cls, user_prompt, target_url="", session_context=""):
        user_prompt = str(user_prompt or "").strip()
        target_url = str(target_url or "").strip()

        if not user_prompt and not target_url:
            return "[WEB ARASTIRMA] Sorgu boş."

        first = _gemini_request(
            _build_search_prompt(user_prompt, target_url, session_context),
            [{"google_search": {}}]
        )

        if not first.get("ok"):
            return "[WEB ARASTIRMA HATASI]\n" + first.get(
                "error", "Bilinmeyen Gemini hatası"
            )

        search_data = first.get("data") or {}
        search_text = _extract_text(search_data)
        search_meta = _extract_search_metadata(search_data)

        normalized_search_sources = _normalize_sources(search_meta["sources"])

        all_urls = _unique(
            ([target_url] if target_url else [])
            + [s.get("url") for s in normalized_search_sources]
            + _extract_urls(search_text)
            + _extract_urls(session_context)
        )
        selected_urls = [u for u in all_urls if u][:MAX_SEARCH_SOURCE_URLS]

        deep_text = ""
        deep_meta = {"sources": []}

        if selected_urls:
            second = _gemini_request(
                _build_deep_prompt(
                    user_prompt, search_text, selected_urls, target_url
                ),
                [{"url_context": {}}]
            )
            if second.get("ok"):
                second_data = second.get("data") or {}
                deep_text = _extract_text(second_data)
                deep_meta = _extract_search_metadata(second_data)

        source_records = (
            list(search_meta["sources"])
            + list(deep_meta.get("sources", []))
        )

        if not source_records:
            source_records = [
                {"title": "Incelenen URL", "url": u}
                for u in selected_urls
            ]

        unique_sources = _normalize_sources(source_records)

        report = [
            "[WEB ARASTIRMA RAPORU]",
            "",
            "[KULLANICI SORUSU]",
            user_prompt,
            "",
            "[GEMINI'NIN GERCEKLESTIRDIGI ARAMA SORGULARI]",
            "\n".join(f"- {q}" for q in search_meta["queries"])
            if search_meta["queries"] else "Metadata içinde arama sorgusu alınamadı.",
            "",
            "[1. ASAMA - GOOGLE SEARCH BULGULARI]",
            _clip(search_text, MAX_SEARCH_TEXT_CHARS)
            if search_text else "Metinsel arama sonucu alınamadı.",
            ""
        ]

        if deep_text:
            report.extend([
                "[2. ASAMA - URL CONTEXT DERIN OKUMA]",
                _clip(deep_text, MAX_DEEP_TEXT_CHARS),
                ""
            ])

        guard_text = apply_web_guard(
            user_prompt=user_prompt,
            search_text=search_text,
            deep_text=deep_text,
            sources=unique_sources,
            queries=search_meta["queries"],
        )

        report.extend([
            "[INCELENEN KAYNAKLAR]",
            _format_sources(unique_sources),
            "",
            guard_text,
            "",
            "[QWEN ICIN KANIT KURALI]",
            "Bu paket web arastirmasindan elde edilen kanittir. "
            "Kaynakta bulunmayan sayilari veya ayrintilari uydurma. "
            "Veri eksikse eksik oldugunu açıkça soyle. "
            "Kullanici tarafindan istenen adet kadar dogrulanmis kayit yoksa "
            "eksik kayitlari kendi hafizandan tamamlama."
        ])

        return _clip("\n".join(report), MAX_FINAL_REPORT_CHARS)


def perform_web_research(prompt, target_url="", session_context=""):
    return WebResearchAgent.research(
        user_prompt=prompt,
        target_url=target_url,
        session_context=session_context
    )
