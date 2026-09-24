# -*- coding: utf-8 -*-
"""
GK Studio V3 - Web Evidence Ledger / Consistency Checker

Bu modül internet bağlantısı yapmaz. Gemini'nin ürettiği web araştırma
paketindeki veri-kaynak eşleşmelerini ve açık hesaplamaları muhafazakar
kurallarla kontrol eder.
"""

import re
from urllib.parse import urlparse


_URL_RE = re.compile(r"https?://[^\s<>\"|]+")
_NUMBER_RE = re.compile(r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b|\b\d+(?:,\d+)?\b")


def _unique(values):
    out = []
    seen = set()
    for value in values or []:
        value = str(value or "").strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _valid_http_url(url):
    try:
        parsed = urlparse(str(url))
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _parse_integer(token):
    token = str(token or "").strip()
    if not token or "," in token:
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", token):
        try:
            return int(token.replace(".", ""))
        except ValueError:
            return None
    try:
        return int(token)
    except ValueError:
        return None


def _clean_url(url):
    return str(url or "").strip().rstrip(".,);]}>")


def _extract_source_urls(sources):
    urls = []
    for src in sources or []:
        if isinstance(src, dict):
            url = _clean_url(src.get("url"))
        else:
            url = _clean_url(src)
        if _valid_http_url(url):
            urls.append(url)
    return _unique(urls)


def _add_evidence(rows, claim, value, source_url):
    claim = str(claim or "").strip()
    value = str(value or "").strip()
    source_url = _clean_url(source_url)
    if not source_url or not _valid_http_url(source_url):
        return
    rows.append({
        "claim": claim or "Belirtilmemiş veri",
        "value": value or "Belirtilmemiş",
        "source_url": source_url,
    })


def parse_explicit_evidence(deep_text):
    """
    Gemini'nin üretmesi istenen iki biçimi okur:

      - Veri: Nisan 2026 | Değer: 80.182 | Kaynak: https://...
      Veri | Değer | Kaynak başlıklı Markdown tablo satırları
    """
    rows = []
    in_table = False

    for raw in str(deep_text or "").splitlines():
        line = raw.strip()

        if not line:
            continue

        low = line.lower()

        if "veri |" in low and "kaynak" in low:
            in_table = True
            continue

        if in_table and re.fullmatch(r"\|?\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|\s*:?-{2,}:?\s*\|?", line):
            continue

        if in_table and "|" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3:
                urls = [_clean_url(u) for u in _URL_RE.findall(line)]
                if urls:
                    claim = cells[0]
                    value = cells[1]
                    _add_evidence(rows, claim, value, urls[0])
                    continue

        if "kaynak:" not in low:
            continue

        urls = [_clean_url(u) for u in _URL_RE.findall(line)]
        if not urls:
            continue

        claim_match = re.search(
            r"\bveri:\s*(.+?)(?:\s*\|\s*(?:değer|deger|adet|sayı|sayi):|\s*\|\s*kaynak:)",
            line,
            re.I,
        )
        if claim_match:
            claim = claim_match.group(1).strip()
        else:
            left = re.split(r"\s*\|\s*kaynak:", line, maxsplit=1, flags=re.I)[0]
            claim = re.sub(r"^\s*veri:\s*", "", left, flags=re.I).strip()

        value_match = re.search(
            r"(?:değer|deger|adet|sayı|sayi):\s*([0-9][0-9\.,]*)",
            line,
            re.I,
        )
        value = value_match.group(1) if value_match else ""
        _add_evidence(rows, claim, value, urls[0])

    unique = []
    seen = set()
    for row in rows:
        key = (
            row["claim"].lower(),
            row["value"].lower(),
            row["source_url"].lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def find_explicit_arithmetic_checks(text):
    checks = []
    pattern = re.compile(
        r"((?:\d{1,3}(?:\.\d{3})|\d+)(?:\s*\+\s*(?:\d{1,3}(?:\.\d{3})|\d+))+)"
        r"\s*=\s*(\d{1,3}(?:\.\d{3})|\d+)"
    )

    for match in pattern.finditer(str(text or "")):
        values = [_parse_integer(part.strip()) for part in match.group(1).split("+")]
        expected = _parse_integer(match.group(2))

        if expected is None or any(value is None for value in values):
            continue

        actual = sum(values)
        checks.append({
            "expression": match.group(0),
            "actual": actual,
            "expected": expected,
            "ok": actual == expected,
        })

    return checks


def find_explicit_totals(text):
    """
    'toplam' kelimesi geçen satırlarda mümkünse 'adet' ile açıkça
    ifade edilen sayıları toplar. Yılları toplam adedi olarak kabul etmez.
    """
    totals = []

    for raw in str(text or "").splitlines():
        line = raw.strip()
        low = line.lower()
        if "toplam" not in low:
            continue

        adet_matches = re.findall(
            r"([0-9][0-9\.]*)\s*(?:adet|adettir|olarak gerçekleşmiştir|olarak gercekleşmistir)",
            line,
            re.I,
        )

        candidates = adet_matches if adet_matches else _NUMBER_RE.findall(line)

        numbers = []
        for token in candidates:
            value = _parse_integer(token)
            if value is None:
                continue
            if 1900 <= value <= 2100:
                continue
            numbers.append((token, value))

        if numbers:
            token, value = numbers[-1]
            totals.append({
                "line": line,
                "value_raw": token,
                "value": value,
            })

    return totals


def build_evidence_ledger(user_prompt, search_text, deep_text, sources):
    source_urls = _extract_source_urls(sources)
    allowed = {url.lower(): url for url in source_urls}

    parsed = parse_explicit_evidence(deep_text)
    bound = []
    seen = set()

    for row in parsed:
        source_url = str(row.get("source_url") or "").strip()
        canonical = allowed.get(source_url.lower())
        if not canonical:
            continue

        row = dict(row)
        row["source_url"] = canonical
        key = (
            row["claim"].lower(),
            row["value"].lower(),
            canonical.lower(),
        )
        if key in seen:
            continue

        seen.add(key)
        bound.append(row)

    bound_urls = _unique(row["source_url"] for row in bound)

    return {
        "requested_prompt": str(user_prompt or "").strip(),
        "bound_evidence": bound,
        "source_urls": source_urls,
        "bound_count": len(bound),
        "unmapped_source_count": max(0, len(source_urls) - len(bound_urls)),
    }


def find_period_total_conflicts(text):
    """
    Aynı istenen dönem için metinde farklı toplamlar varsa tespit eder.
    Özellikle 'son 6 ay' gibi dönem toplamlarında ilk aşamadaki hatalı
    toplam ile ikinci aşamadaki yeniden hesaplanan toplamı ayırır.
    """
    groups = {}

    for raw in str(text or "").splitlines():
        line = " ".join(raw.strip().split())
        low = line.lower()

        if "toplam" not in low:
            continue

        numbers = re.findall(
            r"([0-9][0-9\.]*)\s*(?:adet|adettir)",
            line,
            re.I,
        )
        if not numbers:
            continue

        token = numbers[-1]
        value = _parse_integer(token)
        if value is None:
            continue

        # Yıl gibi küçük sayıları toplam adedi olarak kabul etme.
        if 1900 <= value <= 2100:
            continue

        if "son 6 ay" in low or ("mart" in low and "ağustos" in low):
            key = "mart-2026_agustos-2026"
        elif "ocak-ağustos" in low or "ocak-agustos" in low:
            key = "ocak-agustos-2026"
        elif "ocak-şubat" in low or "ocak-subat" in low:
            key = "ocak-subat-2026"
        else:
            continue

        groups.setdefault(key, []).append(value)

    conflicts = []
    for period, values in groups.items():
        unique_values = _unique(str(v) for v in values)
        if len(unique_values) > 1:
            conflicts.append({
                "period": period,
                "values": [int(v) for v in unique_values],
            })

    return conflicts


def _month_claim_values(evidence_ledger):
    month_words = (
        "ocak", "şubat", "subat", "mart", "nisan", "mayıs", "mayis",
        "haziran", "temmuz", "ağustos", "agustos", "eylül", "eylul",
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september",
    )

    month_pattern = re.compile(
        r"^(?P<month>" + "|".join(month_words) + r")\s+\d{4}(?:\s+otomobil)?(?:\s+satış(?:ları)?|\s+satis(?:lari)?)?$",
        re.I,
    )

    out = []
    for row in (evidence_ledger or {}).get("bound_evidence", []):
        claim = " ".join(str(row.get("claim") or "").split()).strip()
        low = claim.lower()
        value = _parse_integer(row.get("value"))

        # Kümülatif/range verileri (örn. Ocak-Ağustos 2026 Toplam)
        # aylık satış hesabına dahil edilmez.
        if value is None or "toplam" in low or "-" in claim:
            continue

        if month_pattern.fullmatch(low):
            out.append((low, value))

    return out


def build_consistency_report(search_text, deep_text, evidence_ledger=None):
    combined = "\n".join([
        str(search_text or ""),
        str(deep_text or ""),
    ])

    arithmetic = find_explicit_arithmetic_checks(combined)
    totals = find_explicit_totals(combined)
    period_conflicts = find_period_total_conflicts(combined)
    warnings = []
    calculated_month_total = None

    for check in arithmetic:
        if not check["ok"]:
            warnings.append(
                f"Aritmetik uyuşmazlık: {check['expression']} -> "
                f"beklenen {check['expected']}, hesaplanan {check['actual']}."
            )

    for conflict in period_conflicts:
        warnings.append(
            f"Aynı dönem için farklı toplamlar bulundu "
            f"({conflict['period']}): "
            + ", ".join(f"{v:,}".replace(",", ".") for v in conflict["values"])
            + ". Kaynağa dayalı tek bir toplam doğrulanmadan kesin değer sunma."
        )

    month_values = _month_claim_values(evidence_ledger)
    if len(month_values) >= 2:
        calculated_month_total = sum(value for _, value in month_values)
        reported_totals = [item["value"] for item in totals]

        # Metinde ayrıca 564.241 gibi başka dönemlere ait kümülatif
        # toplamlar bulunabilir. Bunları çelişki kabul etmeyiz.
        # Yalnızca aylık hesabın karşılığı hiç bulunmuyorsa uyarırız.
        if calculated_month_total not in reported_totals:
            warnings.append(
                f"Kanıt defterindeki aylık verilerin hesaplanan toplamı "
                f"{calculated_month_total}; buna eşit açık bir toplam "
                "değeri bulunamadı."
            )

    return {
        "status": "Uyarı var." if warnings else "Temel tutarlılık kontrolleri geçti.",
        "warnings": warnings,
        "arithmetic_checks": arithmetic,
        "totals": totals,
        "period_conflicts": period_conflicts,
        "month_evidence_count": len(month_values),
        "calculated_month_total": calculated_month_total,
    }


def strip_embedded_ledger(text):
    """
    Gemini'nin derin okuma cevabındaki kendi [KANIT DEFTERI] bloğunu
    sunum metninden çıkarır. Makine tarafından parse edilen ham metin korunur.
    """
    text = str(text or "")
    marker = "[KANIT DEFTERI]"
    if marker not in text:
        return text

    before, after = text.split(marker, 1)
    next_markers = (
        "[TUTARLILIK KONTROLU]",
        "[WEB GUARD]",
        "[INCELENEN KAYNAKLAR]",
    )

    cut_at = None
    for next_marker in next_markers:
        pos = after.find(next_marker)
        if pos >= 0:
            cut_at = pos if cut_at is None else min(cut_at, pos)

    if cut_at is None:
        return before.rstrip()

    return (before + after[cut_at:]).strip()


def format_evidence_ledger(ledger):
    lines = [
        "[KANIT DEFTERI]",
        f"Kaynak URL sayısı: {len(ledger.get('source_urls', []))}",
        f"Doğrudan veri-kaynak eşleşmesi: {ledger.get('bound_count', 0)}",
        f"Eşleşmesi olmayan kaynak sayısı: {ledger.get('unmapped_source_count', 0)}",
        "",
    ]

    rows = ledger.get("bound_evidence") or []
    if not rows:
        lines.append("Doğrudan veri-kaynak eşleşmesi üretilemedi.")
        return "\n".join(lines)

    lines.extend([
        "Veri | Değer | Kaynak",
        "---|---|---",
    ])

    for row in rows:
        lines.append(
            f"{row['claim']} | {row['value']} | {row['source_url']}"
        )

    return "\n".join(lines)


def format_consistency_report(report):
    lines = [
        "[TUTARLILIK KONTROLU]",
        f"Durum: {report.get('status', 'Belirlenemedi.')}",
    ]

    if report.get("month_evidence_count"):
        lines.append(
            f"Kanıt defterindeki aylık veri sayısı: {report.get('month_evidence_count')}"
        )
    if report.get("calculated_month_total") is not None:
        lines.append(
            f"Kanıt defterinden hesaplanan aylık toplam: {report.get('calculated_month_total')}"
        )

    if report.get("month_evidence_count"):
        lines.append(
            f"Kanıt defterindeki aylık veri sayısı: {report.get('month_evidence_count')}"
        )
    if report.get("calculated_month_total") is not None:
        lines.append(
            f"Kanıt defterinden hesaplanan aylık toplam: {report.get('calculated_month_total')}"
        )

    warnings = report.get("warnings") or []
    if warnings:
        lines.extend([
            "",
            "[UYARILAR]",
        ])
        lines.extend(f"- {warning}" for warning in warnings)

    checks = report.get("arithmetic_checks") or []
    if checks:
        lines.extend([
            "",
            "[ARITMETIK KONTROLLER]",
        ])
        lines.extend(
            f"- {item['expression']} -> {'OK' if item['ok'] else 'HATA'}"
            for item in checks
        )

    return "\n".join(lines)
