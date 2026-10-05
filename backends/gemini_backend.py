# C:\AI_YEREL\GK_STUDIO_V3\backends\gemini_backend.py
# -*- coding: utf-8 -*-
import json
import urllib.request
from config import GEMINI_API_KEY

class GeminiBackend:
    @staticmethod
    def is_healthy():
        """Gemini API anahtarının geçerliliğini ve bağlantısını kontrol eder."""
        if not GEMINI_API_KEY or len(GEMINI_API_KEY) <= 5:
            return False
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def generate_stream(prompt, system_instruction="", images=None):
        """Gemini 2.5 Flash modeline HTTP API üzerinden istek atar."""
        if not GEMINI_API_KEY:
            yield "[GEMINI HATASI]: GEMINI_API_KEY eksik veya .env okunamadı.", True
            return

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        
        full_text = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt
        parts = [{"text": full_text}]
        
        if images:
            for img in images:
                parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img}})

        payload = json.dumps({"contents": [{"parts": parts}]}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                res_data = json.loads(resp.read().decode("utf-8"))
                text = "".join([
                    p.get("text", "") 
                    for p in res_data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
                ])
                yield text, True
        except Exception as e:
            yield f"[GEMINI HATASI]: {str(e)}", True