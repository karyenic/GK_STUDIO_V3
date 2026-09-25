# C:\AI_YEREL\GK_STUDIO_V3\backends\ollama_backend.py
# -*- coding: utf-8 -*-
import json
import base64
import os
import urllib.request
import urllib.error
from config import EMBEDDING_OLLAMA_URL, EMBED_MODEL

# Ollama'nın chat portu (embedding'den farklı!)
OLLAMA_CHAT_URL = "http://localhost:11434"

# Vision için güvenli tavan (IPEX OLLAMA_CONTEXT_LENGTH ile uyumlu)
VISION_MAX_CTX = 2048


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


class OllamaVisionBackend:
    """Görüntü işleme için Ollama /api/chat kullanan backend."""

    @staticmethod
    def _encode_image(image_source: str) -> str:
        """
        image_source: dosya yolu VEYA zaten base64 string.
        Ollama'ya MIME prefix'siz saf base64 gönderiyoruz.
        """
        # Eğer dosya yolu ise oku
        if isinstance(image_source, str) and os.path.isfile(image_source):
            with open(image_source, 'rb') as f:
                return base64.standard_b64encode(f.read()).decode('utf-8')

        # data:image/...;base64,XXXX → sadece XXXX kısmını al
        if isinstance(image_source, str) and image_source.startswith('data:image/'):
            return image_source.split(',', 1)[-1]

        # Düz base64 varsayalım
        return image_source

    @staticmethod
    def generate_stream(model: str, prompt: str, images=None, num_ctx: int = 8192):
        """
        Ollama /api/chat ile streaming vision yanıtı üretir.
        Yield: (content_str, done_bool) tuple'ları
        """
        url = f"{OLLAMA_CHAT_URL}/api/chat"

        # 🎯 GÜVENLİK: num_ctx'i vision için sınırla
        safe_ctx = min(int(num_ctx or VISION_MAX_CTX), VISION_MAX_CTX)

        messages = []
        if images:
            encoded = []
            for img in images:
                e = OllamaVisionBackend._encode_image(img)
                if e:
                    encoded.append(e)

            print(f"[OllamaVision] {len(encoded)} görsel encode edildi "
                  f"(ilk base64 uzunluk: {len(encoded[0]) if encoded else 0})", flush=True)

            messages.append({
                "role": "user",
                "content": prompt,
                "images": encoded
            })
        else:
            messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "num_ctx": safe_ctx,
                "temperature": 0.7,
            }
        }

        body_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        print(f"[OllamaVision] POST {url} → model={model} ctx={safe_ctx} "
              f"images={len(images) if images else 0} payload={len(body_bytes)} byte",
              flush=True)

        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                    except json.JSONDecodeError:
                        continue

                    # 🎯 Ollama bazen stream içinde hata döner
                    if "error" in chunk:
                        err = chunk.get("error", "bilinmeyen hata")
                        print(f"[OllamaVision] Stream error: {err}", flush=True)
                        yield (f"\n[Ollama Vision Stream Hatası]: {err}", True)
                        return

                    msg = chunk.get("message", {})
                    text = msg.get("content", "")
                    done = bool(chunk.get("done", False))

                    if text or done:
                        yield (text, done)

                    if done:
                        return

        except urllib.error.HTTPError as e:
            # 🎯 KRİTİK: HTTP hatasının GERÇEK gövdesini oku
            err_body = ""
            try:
                err_body = e.read().decode('utf-8', errors='ignore')
            except Exception:
                pass

            # JSON ise parse et
            err_msg = err_body
            try:
                parsed = json.loads(err_body)
                if isinstance(parsed, dict) and "error" in parsed:
                    err_msg = parsed["error"]
            except Exception:
                pass

            print(f"[OllamaVision] HTTP {e.code} → {err_msg}", flush=True)
            yield (f"\n[Ollama Vision HTTP {e.code}]: {err_msg}", True)

        except Exception as e:
            print(f"[OllamaVision] {type(e).__name__}: {e}", flush=True)
            yield (f"\n[Ollama Vision Hatası]: {type(e).__name__}: {str(e)}", True)