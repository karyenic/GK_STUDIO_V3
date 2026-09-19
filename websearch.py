# C:\AI_YEREL\GK_STUDIO_V3\websearch.py
# -*- coding: utf-8 -*-
"""
Web arama uyumluluk katmani.
Gercek arastirma web_research.py icindeki WebResearchAgent tarafindan yapilir.
"""

import re

from web_research import perform_web_research


_URL_RE = re.compile(r"https?://[^\s<>\"']+|www\.[^\s<>\"']+", re.I)

_WEB_KEYWORDS = [
    "güncel", "guncel", "araştır", "arastir", "internetten", "internet", "web",
    "siteyi incele", "siteyi araştır", "siteyi arastir", "web üzerinden",
    "web uzerinden", "son durum", "son haber", "bugün", "bugun", "bu ay",
    "son ay", "son 6 ay", "son altı ay", "son 12 ay", "fiyat", "fiyatı",
    "fiyati", "satış", "satis", "satıldı", "satildi", "kaç adet", "kac adet",
    "istatistik", "veri", "pazar payı", "pazar payi", "ciro", "katalog",
    "pdf", "kaynak", "karşılaştır", "karsilastir", "incele", "bul", "ara"
]


def extract_web_target(text):
    match = _URL_RE.search(str(text or ""))
    if not match:
        return ""
    return match.group(0).rstrip(".,);]}>")


def needs_web_search(text, has_web_context=False):
    if has_web_context:
        return False

    p = str(text or "").strip().lower()
    if not p:
        return False

    if _URL_RE.search(p):
        return True

    return any(keyword in p for keyword in _WEB_KEYWORDS)


def perform_web_search(prompt, target_url="", session_context=""):
    return perform_web_research(
        prompt=prompt,
        target_url=target_url,
        session_context=session_context
    )
