# C:\AI_YEREL\GK_STUDIO_V3\backends\ipex_backend.py
# -*- coding: utf-8 -*-
import json
import urllib.request
from config import IPEX_RUNNER_URL

class IPEXBackend:
    @staticmethod
    def is_healthy():
        """Port 59584 IPEX Runner servisinin ayakta olup olmadığını doğrular."""
        try:
            req = urllib.request.Request(f"{IPEX_RUNNER_URL}/health", headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                return resp.status == 200 and data.get("status") == 0 and data.get("progress") == 1
        except Exception:
            return False

    @staticmethod
    def generate_stream(prompt, model=None, num_ctx=16384, temperature=0.2):
        """IPEX Runner uç noktasına doğrudan canlı yayın (stream) isteği atar."""
        payload = {
            "prompt": prompt,
            "stream": True,
            "n_predict": 2048,
            "temperature": temperature,
            "top_k": 40,
            "top_p": 0.95,
            "ctx_size": num_ctx
        }
        
        # Eğer runner çoklu model destekliyorsa model adını payload'a ekle
        if model:
            payload["model"] = model

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            f"{IPEX_RUNNER_URL}/completion",
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                while True:
                    line = resp.readline()
                    if not line:
                        break
                    line = line.strip()
                    if line:
                        try:
                            chunk = json.loads(line.decode("utf-8", errors="replace"))
                            content = chunk.get("content", "")
                            done = chunk.get("done", False)
                            yield content, done
                            if done:
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[IPEX SÜRÜCÜ HATASI]: {str(e)}", True