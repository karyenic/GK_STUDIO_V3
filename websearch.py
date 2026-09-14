# C:\AI_YEREL\GK_STUDIO_V3\websearch.py
# -*- coding: utf-8 -*-
import json
import urllib.request
from config import GEMINI_API_KEY

def needs_web_search(text, has_web_context=False):
    """Sorgunun canlı web taraması gerektirip gerektirmediğini analiz eder."""
    if has_web_context:
        return False

    p = (text or '').lower()
    is_explicit_url = any(k in p for k in ['www.', 'http://', 'https://'])
    keywords = ['güncel', 'araştır', 'merkez bankası', 'tcmb', 'siteyi incele', 'web üzerinden', 'internet', 'fiyatı', 'son durum']
    
    return is_explicit_url or any(kw in p for kw in keywords)

def perform_web_search(prompt):
    """Gemini 2.5 Flash Google Search grounding aracını kullanarak canlı web taraması yapar."""
    if not GEMINI_API_KEY:
        return "[UYARI: Gemini API anahtarı tanımlı olmadığı için web taraması yapılamadı.]"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    search_prompt = (
        f"Lütfen şu hedef web sitesini veya konuyu canlı olarak derinlemesine tara: {prompt}\n\n"
        "Talimatlar:\n"
        "1. Sitedeki GERÇEK iletişim bilgilerini (açık adres, telefon numaraları, e-posta) eksiksiz çıkar.\n"
        "2. Sitede yer alan tüm E-Katalog, PDF, çizim ve indirilebilir dosya bağlantılarını tam URL ile listele.\n"
        "3. Veri bulamazsan ASLA tahmin yapma; verinin taranan kaynakta yer almadığını açıkça belirt."
    )

    payload = {
        "contents": [{"parts": [{"text": search_prompt}]}],
        "tools": [{"googleSearch": {}}]
    }

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            parts = res_json.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            web_text = "".join([p.get("text", "") for p in parts])
            return web_text if web_text else "[UYARI: Web aramasından sonuç dönmedi.]"
    except Exception as e:
        return f"[UYARI: Web taraması sırasında hata oluştu: {str(e)}]"