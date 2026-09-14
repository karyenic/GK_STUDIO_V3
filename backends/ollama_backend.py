# C:\AI_YEREL\GK_STUDIO_V3\backends\ollama_backend.py
# -*- coding: utf-8 -*-
import json
import urllib.request
from config import EMBEDDING_OLLAMA_URL, EMBED_MODEL

class OllamaBackend:
    @staticmethod
    def is_healthy():
        """Port 11435 Embedding Ollama servisinin durumunu kontrol eder."""
        try:
            req = urllib.request.Request(f"{EMBEDDING_OLLAMA_URL}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                return resp.status == 200
        except Exception:
            return False

    @staticmethod
    def get_embedding(text):
        """RAG/ChromaDB için vektör üretir."""
        url = f"{EMBEDDING_OLLAMA_URL}/api/embeddings"
        payload = json.dumps({"model": EMBED_MODEL, "prompt": text}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                emb = data.get("embedding")
                if not emb:
                    raise RuntimeError(f"Embedding boş döndü. '{EMBED_MODEL}' modeli yüklü mü?")
                return emb
        except Exception as e:
            raise RuntimeError(f"Embedding servisi hatası: {str(e)}")