# -*- coding: utf-8 -*-
"""
GK Studio V3 - Web Guard

Web arastirmasindan Qwen'e giden paketi basit kurallarla disipline eder.
Amac: kaynaklari ve eksik veri durumunu görünür tutmak, istenen adet ile
elde edilen satirlar arasindaki farki belirtmek ve Qwen'in eksik veriyi
kendi hafizasindan tamamlamasini engellemek.

Bu modül internet baglantisi yapmaz.
"""

import re


_NUMBER_REQUEST_PATTERNS = (
    re.compile(r"\b(?:ilk|top|en çok|en cok)\s+(\d{1,3})\b", re.I),
    re.compile(r"\b(\d{1,3})\s+(?:marka|firma|şirket|sirket|ülke|ulke|model|ürün|urun|kayıt|kayit)\b", re.I),
)


def requested_count(text):
    text = str(text or "")
    for pattern in _NUMBER_REQUEST_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                return None
    return None


def _table_row_count(text):
    count = 0
    in_table = False
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if "|" not in line:
            if in_table and line:
                in_table = False
            continue

        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2:
            continue

        if all(set(c.replace(":", "").replace("-", "").replace(" ", "")) <= set() for c in cells):
            continue

        if all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells):
            in_table = True
            continue

        header_words = " ".join(cells).lower()
        if any(k in header_words for k in (
            "marka", "adet", "firma", "şirket", "sirket", "ülke",
            "ulke", "model", "satış", "satis", "fiyat", "ciro"
        )):
            in_table = True
            continue

        if in_table:
            count += 1

    return count


def observed_rows(text):
    # Sadece acikca markdown tablo satirlarini say.
    # Serbest metin icindeki 1., 2., 3. gibi numaralar kaynak listesi de olabilir.
    return _table_row_count(text)


def _unique_urls(urls):
    out = []
    seen = set()
    for url in urls or []:
        url = str(url or "").strip()
        if not url:
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(url)
    return out


def apply_web_guard(
    user_prompt,
    search_text,
    deep_text,
    sources,
    queries,
):
    requested = requested_count(user_prompt)

    combined_text = "\n".join([
        str(search_text or ""),
        str(deep_text or ""),
    ])
    rows = observed_rows(combined_text)

    urls = _unique_urls(
        [src.get("url") for src in (sources or []) if isinstance(src, dict)]
    )

    warnings = []

    if not urls:
        warnings.append(
            "Kaynak URL'si alınamadı; sayısal veya spesifik iddialar "
            "doğrulanmış veri gibi sunulmamalı."
        )

    if requested is not None and rows and rows < requested:
        warnings.append(
            f"Kullanıcı {requested} kayıt istedi; araştırma paketinde "
            f"yaklaşık {rows} satır tespit edildi. Eksik kayıtları tahmin etme."
        )

    if requested is not None and rows == 0:
        warnings.append(
            f"Kullanıcı {requested} kayıt istedi ancak yapılandırılmış satır "
            "tespit edilemedi. Qwen eksik listeyi kendi bilgisinden doldurmamalı."
        )

    if not warnings:
        warnings.append("Temel web guard kontrolleri geçti; yine de kaynak kurallarına uy.")

    lines = [
        "[WEB GUARD]",
        f"İstenen kayıt sayısı: {requested if requested is not None else 'belirtilmedi'}",
        f"Araştırma paketinde tespit edilen tablo/numaralı satır: {rows}",
        f"Kaynak URL sayısı: {len(urls)}",
        "",
        "[WEB GUARD UYARILARI]",
    ]

    for warning in warnings:
        lines.append(f"- {warning}")

    lines.extend([
        "",
        "[WEB GUARD KURALI]",
        "Qwen yalnızca bu araştırma paketinde bulunan kanıtları kullanmalıdır.",
        "Eksik kayıt, sayı, ciro, tarih veya sıralamayı hafızadan tamamlamamalıdır.",
        "Kullanıcı daha fazla kayıt istediği halde yeterli kanıt yoksa eksik olduğunu açıkça belirtmelidir.",
        "Kaynak URL'si olmayan spesifik bir veri doğrulanmış web verisi gibi sunulmamalıdır.",
        "",
        "[WEB ARAŞTIRMA SORGULARI]",
    ])

    if queries:
        lines.extend(f"- {q}" for q in _unique_urls(queries))
    else:
        lines.append("- Arama sorgusu metadata içinde alınamadı.")

    lines.extend([
        "",
        "[WEB KAYNAK URL'LERİ]",
    ])

    if urls:
        lines.extend(f"- {u}" for u in urls)
    else:
        lines.append("- URL bulunamadı.")

    return "\n".join(lines)
