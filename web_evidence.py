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
    'toplam' kelimesinin bulunduğu aynı satırdaki son açık tam sayıyı toplar.
    Bu kasıtlı olarak sınırlıdır; serbest metindeki her sayıyı toplam kabul etmez.
    """
    totals = []

    for raw in str(text or "").splitlines():
        line = raw.strip()
        if "toplam" not in line.lower():
            continue

        numbers = []
        for token in _NUMBER_RE.findall(line):
            value = _parse_integer(token)
            if value is not None:
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


def build_consistency_report(search_text, deep_text):
    combined = "\n".join([
        str(search_text or ""),
        str(deep_text or ""),
    ])

    arithmetic = find_explicit_arithmetic_checks(combined)
    totals = find_explicit_totals(combined)
    warnings = []

    for check in arithmetic:
        if not check["ok"]:
            warnings.append(
                f"Aritmetik uyuşmazlık: {check['expression']} -> "
                f"beklenen {check['expected']}, hesaplanan {check['actual']}."
            )

    distinct_totals = _unique(str(item["value"]) for item in totals)
    if len(distinct_totals) > 1:
        warnings.append(
            "Metin içinde birden fazla farklı açık toplam değeri bulundu: "
            + ", ".join(distinct_totals)
            + ". Tek bir toplam olarak sunmadan önce kaynakları kontrol et."
        )

    return {
        "status": "Uyarı var." if warnings else "Temel tutarlılık kontrolleri geçti.",
        "warnings": warnings,
        "arithmetic_checks": arithmetic,
        "totals": totals,
    }


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
