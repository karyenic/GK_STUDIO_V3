# C:\AI_YEREL\GK_STUDIO_V3\models.py
# -*- coding: utf-8 -*-
from config import (
    FALLBACK_LOCAL, CLOUD_MODELS, 
    HARD_CAP_MAX, HARD_CAP_MID, HARD_CAP_LOW
)
import urllib.request
import json
from config import EMBEDDING_OLLAMA_URL


def get_num_ctx(model_name, extra_chars=0, is_project=False, is_vision=False):
    """
    VRAM ve RAM taşmasını önleyen, 14B modellerde 32K tavan sağlayan 
    akıllı dinamik context hesaplama algoritması.
    """
    # ✅ Vision dalı — model profiline göre ayrı ctx döner
    if is_vision:
        from config import VISION_CTX_PROFILE, DEFAULT_VISION_CTX
        m_lower = (model_name or "").lower()
        for pattern, ctx_val in VISION_CTX_PROFILE.items():
            if pattern in m_lower:
                return ctx_val
        return DEFAULT_VISION_CTX

    tiers = [4096, 8192, 16384, 32768]
    m_lower = (model_name or "").lower()

    # 1. Model sınıfına göre VRAM tavanı (hard_cap) belirleme
    if any(k in m_lower for k in ["14b", "13b", "15b"]):
        hard_cap = HARD_CAP_MAX  # 32768
    elif any(k in m_lower for k in ["2b", "3b", "1b"]):
        hard_cap = HARD_CAP_LOW  # 8192
    else:
        hard_cap = HARD_CAP_MAX if is_project else HARD_CAP_MID  # 32768 / 16384

    # 2. Karakter katsayısı üzerinden tahmini token ihtiyacı
    estimated_tokens = int(extra_chars / 2.5)
    needed = estimated_tokens + 2048  # Yanıt üretimi için koruma tamponu

    # 3. Proje aktifse veya büyük dosya paketi geldiyse tavanı kullan
    if is_project or extra_chars > 20000:
        return hard_cap

    # 4. İhtiyaca en yakın en küçük katmana yuvarla (VRAM koruması)
    for t in tiers:
        if t >= needed:
            return min(t, hard_cap)

    return hard_cap


def get_installed_ollama_models():
    """Embedding Ollama servisinden (Port 11435) yüklü modelleri çeker."""
    try:
        req = urllib.request.Request(f"{EMBEDDING_OLLAMA_URL}/api/tags")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name") for m in data.get("models", [])]
    except Exception:
        pass
    return []


def get_categorized_models():
    """Arayüz için modelleri yetenek sınıflarına ayırır."""
    local_models = get_installed_ollama_models()
    if not local_models:
        local_models = FALLBACK_LOCAL
    if "auto" not in local_models:
        local_models.append("auto")

    vision_models = [
        m for m in local_models 
        if any(k in m.lower() for k in ["vision", "moondream", "granite"]) and "qwen3-vl" not in m.lower()
    ]
    coder_models = [m for m in local_models if "coder" in m.lower()]
    reasoning_models = [m for m in local_models if any(k in m.lower() for k in ["r1", "deepseek"])]

    assigned = set(vision_models + coder_models + reasoning_models + ["auto"])
    pure_local = [m for m in local_models if m not in assigned]

    return {
        "local": pure_local,
        "coder": coder_models,
        "reasoning": reasoning_models,
        "vision": vision_models,
        "cloud": CLOUD_MODELS
    }