# C:\AI_YEREL\GK_STUDIO_V3\config.py
# -*- coding: utf-8 -*-
import os
import sys

# Windows konsol UTF-8 desteği
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

# .env Dosyasından Gemini API Anahtarını BOM Korumalı Okuma
GEMINI_API_KEY = ""
if os.path.exists(ENV_FILE):
    try:
        with open(ENV_FILE, "r", encoding="utf-8-sig") as ef:
            for line in ef:
                if "GEMINI_API_KEY" in line and not line.strip().startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) > 1:
                        GEMINI_API_KEY = parts[1].strip().strip('"').strip("'").split("#")[0].strip()
    except Exception as e:
        print(f"[CONFIG UYARI] .env okunurken hata: {e}")

# PORT YAPILANDIRMASI
STUDIO_PORT = 5000
IPEX_RUNNER_PORT = 59584
EMBEDDING_OLLAMA_PORT = 11435
GATEWAY_PORT = 11434

# SERVİS URL'LERİ
IPEX_RUNNER_URL = f"http://127.0.0.1:{IPEX_RUNNER_PORT}"
EMBEDDING_OLLAMA_URL = f"http://127.0.0.1:{EMBEDDING_OLLAMA_PORT}"
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"

# KLASÖR VE DİZİN YAPISI
CONV_DIR = os.path.join(BASE_DIR, "conversations")
EXPORTS_DIR = os.path.join(BASE_DIR, "exports")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
CHAT_DIR = os.path.join(BASE_DIR, "chat_history")
EXCELS_DIR = os.path.join(BASE_DIR, "excel")
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
PROJECTS_FILE = os.path.join(BASE_DIR, "projects_config.json")

# Gerekli Dizimleri Otomatik Oluştur
for d in [CONV_DIR, EXPORTS_DIR, UPLOADS_DIR, CHAT_DIR, EXCELS_DIR, CHROMA_DIR, LOGS_DIR]:
    os.makedirs(d, exist_ok=True)

# MODEL VE EMBEDDING VARSAYILANLARI
DEFAULT_LOCAL_MODEL = "qwen2.5-coder:7b"
EMBED_MODEL = "nomic-embed-text"
CLOUD_MODELS = ["gemini-2.5-flash"]

FALLBACK_LOCAL = [
    "qwen2.5:7b", "deepseek-r1:7b", "gemma4:latest", "qwen2.5-coder:7b", 
    "llama3.2:3b", "gemma2:2b", "deepseek-r1-64k:latest"
]

# CONTEXT HESAPLAMA PARAMETRELERİ
HARD_CAP_MAX = 32768   # 14B ve Proje Modları İçin VRAM Tavanı
HARD_CAP_MID = 16384   # 7B-8B Modeller İçin Standart Tavan
HARD_CAP_LOW = 8192    # 2B-3B Modeller İçin Tavan

# SİSTEM PROFILLERI VE ROLLER
SYSTEM_PROFILE = """[MASTER SİSTEM PROFİLİ & LOKAL HİBRİT MİMARİ SÖZLEŞMESİ]
- Kullanıcı / Sahip: Güven (İzmir, Türkiye - Otomotiv yan sanayi, yazılım geliştirici).
- Donanım Altyapısı: Dell 16250 Plus, 32 GB RAM, Intel Arc GPU, Windows 11 (64-bit).
- Çalışma İlkeleri: Asla varsayım yapma. Tüm yanıtlarını istisnasız ve SADECE TÜRKÇE dilinde ver."""

ROLE_PROMPTS = {
    "default": "Sen nazik, net ve çözüm odaklı genel bir yapay zeka asistanısın.",
    "coder": "Sen kıdemli bir yazılım mimarısın. Kod yanıtlarını eksiksiz, temiz ve Markdown formatında ver.",
    "writer": "Sen teknik ve idari işlerde uzmanlaşmış kıdemli bir teknik yazarsın.",
    "analyst": "Sen veri ve iş analistisin. Yanıtları maddeler ve tablolar halinde sun.",
    "engineer": "Sen otomotiv ve imalat mühendisliği uzmanısın. Toleranslar ve malzeme bilgisine odaklan."
}