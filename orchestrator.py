# C:\AI_YEREL\GK_STUDIO_V3\orchestrator.py
# -*- coding: utf-8 -*-
import subprocess
import sys
import os
import time
import threading
import urllib.request
import json
from config import BASE_DIR, IPEX_RUNNER_PORT, STUDIO_PORT

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

COLOR_GPU = "\033[92m[GPU RUNNER 59584]\033[0m"
COLOR_EMBED = "\033[96m[EMBED OLLAMA 11435]\033[0m"
COLOR_CHAT = "\033[94m[CHAT OLLAMA 11434]\033[0m"      # ✅ YENİ
COLOR_STUDIO = "\033[93m[GK STUDIO 5000]\033[0m"
COLOR_SYS = "\033[95m[SYSTEM]\033[0m"


def stream_log(process, prefix):
    for line in iter(process.stdout.readline, ''):
        if line:
            print(f"{prefix} {line.strip()}", flush=True)


def main():
    print(f"\n{COLOR_SYS} ========================================================", flush=True)
    print(f"{COLOR_SYS} GK STUDIO V3 - MODÜLER ORKESTRATÖR BAŞLATILIYOR        ", flush=True)
    print(f"{COLOR_SYS} ========================================================", flush=True)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["OLLAMA_NUM_GPU"] = "999"
    env["ONEAPI_DEVICE_SELECTOR"] = "level_zero:0"
    env["ZES_ENABLE_SYSMAN"] = "1"
    env["SYCL_CACHE_PERSISTENT"] = "1"
    env["OLLAMA_FLASH_ATTENTION"] = "false"
    env["NO_PROXY"] = "localhost,127.0.0.1"

    ipex_dir = r"C:\AI_IPEX\Ollama\portable"
    runner_exe = os.path.join(ipex_dir, "ollama-lib.exe")
    model_path = r"C:\Users\karye\.ollama\models\blobs\sha256-60e05f2100071479f596b964f89f510f057ce397ea22f2833a0cfe029bfc2463"

    # ============================================================
    # 1. IPEX GPU Runner (Port 59584)
    # ============================================================
    runner_cmd = [
        runner_exe, "runner",
        "--model", model_path,
        "--ctx-size", "32768",
        "--batch-size", "512",
        "--n-gpu-layers", "999",
        "--threads", "4",
        "--no-mmap",
        "--parallel", "1",
        "--port", str(IPEX_RUNNER_PORT),
        "--verbose"
    ]

    print(f"{COLOR_SYS} [1/4] IPEX GPU Runner başlatılıyor (Port {IPEX_RUNNER_PORT} / 32K Context)...", flush=True)
    p_runner = subprocess.Popen(
        runner_cmd, cwd=ipex_dir, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )
    t_runner = threading.Thread(target=stream_log, args=(p_runner, COLOR_GPU), daemon=True)
    t_runner.start()

    # IPEX Sağlık Kontrolü
    ready = False
    for _ in range(30):
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{IPEX_RUNNER_PORT}/health")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == 0 and data.get("progress") == 1:
                    ready = True
                    break
        except Exception:
            pass
        time.sleep(1)

    if not ready:
        print(f"{COLOR_SYS} [HATA] IPEX Runner 30 saniye içinde yanıt vermedi.", flush=True)
        p_runner.kill()
        sys.exit(1)

    print(f"{COLOR_SYS} [OK] IPEX GPU Runner hazır!", flush=True)

    # ============================================================
    # 2. Embedding Ollama Servisi (Port 11435)
    # ============================================================
    print(f"{COLOR_SYS} [2/4] Embedding Ollama Servisi başlatılıyor (Port 11435)...", flush=True)
    env_embed = env.copy()
    env_embed["OLLAMA_HOST"] = "127.0.0.1:11435"

    p_embed = subprocess.Popen(
        [os.path.join(ipex_dir, "ollama.exe"), "serve"],
        cwd=ipex_dir, env=env_embed,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )
    t_embed = threading.Thread(target=stream_log, args=(p_embed, COLOR_EMBED), daemon=True)
    t_embed.start()
    time.sleep(3)

    # ============================================================
    # 3. Chat Ollama Servisi (Port 11434)  ✅ YENİ ADIM
    # ============================================================
    print(f"{COLOR_SYS} [3/4] Chat Ollama Servisi başlatılıyor (Port 11434 - Vision)...", flush=True)
    env_chat = env.copy()
    env_chat["OLLAMA_HOST"] = "127.0.0.1:11434"
    env_chat["OLLAMA_CONTEXT_LENGTH"] = "4096"
    env_chat["OLLAMA_KEEP_ALIVE"] = "10m"

    p_chat = subprocess.Popen(
        [os.path.join(ipex_dir, "ollama.exe"), "serve"],
        cwd=ipex_dir, env=env_chat,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )
    t_chat = threading.Thread(target=stream_log, args=(p_chat, COLOR_CHAT), daemon=True)
    t_chat.start()
    time.sleep(3)

    # Chat Ollama sağlık kontrolü
    chat_ready = False
    for _ in range(15):
        try:
            req = urllib.request.Request("http://127.0.0.1:11434/api/tags")
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    chat_ready = True
                    break
        except Exception:
            pass
        time.sleep(1)

    if chat_ready:
        print(f"{COLOR_SYS} [OK] Chat Ollama (11434) hazır - Vision aktif!", flush=True)
    else:
        print(f"{COLOR_SYS} [UYARI] Chat Ollama 15 sn içinde yanıt vermedi. Vision çalışmayabilir.", flush=True)

    # ============================================================
    # 4. Flask App (Port 5000)
    # ============================================================
    print(f"{COLOR_SYS} [4/4] GK STUDIO V3 (app.py) başlatılıyor...", flush=True)
    p_studio = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=BASE_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1
    )
    t_studio = threading.Thread(target=stream_log, args=(p_studio, COLOR_STUDIO), daemon=True)
    t_studio.start()

    print(f"\n{COLOR_SYS} ========================================================", flush=True)
    print(f"{COLOR_SYS} GK STUDIO V3 HAZIR! Web Arayüz: http://127.0.0.1:{STUDIO_PORT}", flush=True)
    print(f"{COLOR_SYS} ========================================================\n", flush=True)

    try:
        p_studio.wait()
    except KeyboardInterrupt:
        print(f"\n{COLOR_SYS} Kapatılıyor...", flush=True)
    finally:
        p_studio.kill()
        p_chat.kill()      # ✅ YENİ
        p_embed.kill()
        p_runner.kill()


if __name__ == "__main__":
    main()