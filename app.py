# C:\AI_YEREL\GK_STUDIO_V3\app.py
# -*- coding: utf-8 -*-
import os
import json
import time
import subprocess
import threading
import psutil
import openpyxl
from flask import Flask, request, jsonify, send_from_directory, send_file, Response, stream_with_context, make_response
from config import (
    BASE_DIR, CONV_DIR, EXPORTS_DIR, UPLOADS_DIR, CHAT_DIR,
    EXCELS_DIR, PROJECTS_FILE, STUDIO_PORT
)
from models import get_categorized_models
from gateway import AIGateway
from backends.gemini_backend import GeminiBackend
from backends.ipex_backend import IPEXBackend
from backends.ollama_backend import OllamaBackend
from rag import index_project_folder, clear_project_index

app = Flask(__name__, static_folder="static", template_folder="static")

_sys_cache = {"cpu": 0, "ram": 0, "gpu": 0, "gpu_info": "CPU: %0 | RAM: %0 | GPU: %0", "active": False}
_sys_lock = threading.Lock()

def _system_monitor_loop():
    while True:
        try:
            cpu_val = int(psutil.cpu_percent(interval=None))
            ram_val = int(psutil.virtual_memory().percent)

            runner_active = False
            for proc in psutil.process_iter(['name']):
                try:
                    pname = str(proc.info.get('name') or '').lower()
                    if 'ollama' in pname or 'ipex' in pname or 'python' in pname:
                        runner_active = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            gpu_val = 0
            try:
                ps_script = (
                    "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine "
                    "| Where-Object { $_.UtilizationPercentage -gt 0 } "
                    "| Measure-Object -Property UtilizationPercentage -Sum "
                    "| Select-Object -ExpandProperty Sum"
                )
                cmd = ["powershell", "-NoProfile", "-Command", ps_script]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
                if res.stdout and res.stdout.strip():
                    gpu_val = int(float(res.stdout.strip().replace(',', '.')))
                    if gpu_val > 100:
                        gpu_val = 100
            except Exception:
                gpu_val = 0

            info_str = f"CPU: %{cpu_val} | RAM: %{ram_val} | GPU: %{gpu_val}"

            with _sys_lock:
                _sys_cache["cpu"] = cpu_val
                _sys_cache["ram"] = ram_val
                _sys_cache["gpu"] = gpu_val
                _sys_cache["gpu_info"] = info_str
                _sys_cache["active"] = runner_active or (gpu_val > 0)

        except Exception:
            pass

        time.sleep(2.5)

threading.Thread(target=_system_monitor_loop, daemon=True).start()

@app.after_request
def add_no_cache_headers(response):
    if request.path.startswith(('/static/', '/js/', '/css/')):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

@app.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'js'), filename)

@app.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(os.path.join(BASE_DIR, 'static', 'css'), filename)

def load_projects_config():
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_projects_config(config):
    try:
        with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        return True
    except OSError:
        return False

@app.route('/')
def index():
    response = make_response(send_from_directory('static', 'index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@app.route('/api/status', methods=['GET'])
@app.route('/status', methods=['GET'])
def status():
    with _sys_lock:
        sys_info = _sys_cache["gpu_info"]
        gpu_active = _sys_cache["active"]

    return jsonify({
        "ollama": OllamaBackend.is_healthy(),
        "gpu": gpu_active,
        "gpu_info": sys_info,
        "gemini": GeminiBackend.is_healthy()
    })

@app.route('/api/shutdown', methods=['POST'])
@app.route('/shutdown', methods=['POST'])
def shutdown():
    def stop_server():
        time.sleep(0.5)
        os._exit(0)
    threading.Thread(target=stop_server).start()
    return jsonify({"status": "success", "message": "GK Studio kapatılıyor..."})

@app.route('/api/models', methods=['GET'])
@app.route('/models', methods=['GET'])
def models():
    return jsonify(get_categorized_models())

@app.route('/api/chat', methods=['POST'])
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json or {}
    return Response(
        stream_with_context(AIGateway.process_chat_stream(data)),
        mimetype='text/event-stream'
    )

@app.route('/api/projects/list', methods=['GET'])
def api_list_projects():
    return jsonify({"status": "success", "projects": load_projects_config()})

@app.route('/api/projects/add', methods=['POST'])
def api_add_project():
    try:
        data = request.get_json(silent=True) or {}
        proj_name = data.get("name", "").strip()
        raw_path = data.get("path", "").strip().strip('"').strip("'")

        if not proj_name or not raw_path:
            return jsonify({"status": "error", "message": "Proje adı ve dizin yolu zorunludur."}), 400

        proj_path = os.path.abspath(os.path.expanduser(raw_path))
        if not os.path.exists(proj_path):
            return jsonify({"status": "error", "message": f"Dizin bulunamadı: {proj_path}"}), 400

        clear_project_index(proj_name)

        config = load_projects_config()
        config[proj_name] = {
            "path": proj_path,
            "default_model": data.get("default_model", "auto").strip(),
            "created_at": time.time(),
            "indexed": False
        }
        save_projects_config(config)
        return jsonify({"status": "success", "message": f"'{proj_name}' projesi eklendi."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/projects/index', methods=['POST'])
def api_index_project():
    try:
        data = request.get_json(silent=True) or {}
        proj_name = data.get("name", "").strip()
        config = load_projects_config()
        proj = config.get(proj_name)
        if not proj:
            return jsonify({"status": "error", "message": "Proje bulunamadı."}), 404

        res = index_project_folder(proj_name, proj["path"])
        if res.get("status") == "success":
            proj["indexed"] = True
            proj["indexed_chunk_count"] = res.get("chunk_count")
            proj["indexed_file_count"] = res.get("file_count")
            proj["indexed_at"] = time.time()
            config[proj_name] = proj
            save_projects_config(config)
        return jsonify(res)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/projects/delete', methods=['POST'])
def api_delete_project():
    try:
        data = request.get_json(silent=True) or {}
        proj_name = data.get("name", "").strip()
        config = load_projects_config()
        if proj_name in config:
            del config[proj_name]
            save_projects_config(config)
            clear_project_index(proj_name)
            return jsonify({"status": "success", "message": f"'{proj_name}' projesi silindi."})
        return jsonify({"status": "error", "message": "Proje bulunamadı."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/load-conversations', methods=['GET'])
def load_conversations():
    all_convs = {}
    latest_id = None
    max_id = 1
    os.makedirs(CHAT_DIR, exist_ok=True)
    for fn in os.listdir(CHAT_DIR):
        if fn.endswith('.json'):
            try:
                with open(os.path.join(CHAT_DIR, fn), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for cid, c in data.get('conversations', {}).items():
                        # Üretim durumu çalışma zamanına aittir; kalıcı olmamalıdır.
                        c['isGenerating'] = False
                        c.pop('abortCtrl', None)
                        all_convs[cid] = c
                    if data.get('currentConvId'):
                        latest_id = data.get('currentConvId')
                    if data.get('nextId', 1) > max_id:
                        max_id = data.get('nextId', 1)
            except (json.JSONDecodeError, OSError):
                pass
    return jsonify({'found': bool(all_convs), 'data': {'conversations': all_convs, 'currentConvId': latest_id, 'nextId': max_id}})

@app.route('/save-conversations', methods=['POST'])
def save_conversations():
    data = request.get_json() or {}
    convs = data.get('conversations', {})
    cur_id = data.get('currentConvId')
    next_id = data.get('nextId', 1)
    os.makedirs(CHAT_DIR, exist_ok=True)
    groups = {}
    for cid, c in convs.items():
        # isGenerating ve abortCtrl yalnızca tarayıcı çalışma durumudur.
        # Kalıcı sohbete yazılmaz; böylece bitmiş sohbetler sonsuza kadar "düşünüyor" kalmaz.
        safe_c = dict(c)
        safe_c['isGenerating'] = False
        safe_c.pop('abortCtrl', None)

        m = (safe_c.get('model') or 'default_model').replace(":", "_").replace("\\", "_").replace("/", "_")
        if m not in groups:
            groups[m] = {}
        groups[m][cid] = safe_c

    for m, g in groups.items():
        try:
            with open(os.path.join(CHAT_DIR, f"{m}.json"), 'w', encoding='utf-8') as f:
                json.dump({"conversations": g, "currentConvId": cur_id if cur_id in g else None, "nextId": next_id}, f, ensure_ascii=False, indent=4)
        except OSError:
            pass
    return jsonify({"status": "success"})

@app.route('/markdown-to-excel', methods=['POST'])
def markdown_to_excel():
    data = request.json or {}
    md_text = data.get('markdown_text', '')
    if not md_text:
        return jsonify({"error": "Metin bulunamadı"}), 400
    lines = md_text.splitlines()
    table_lines = [l for l in lines if '|' in l and not l.strip().startswith('|---')]
    if not table_lines:
        return jsonify({"error": "Tablo bulunamadı"}), 400

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Stüdyo Tablo"
    for line in table_lines:
        parts = [p.strip() for p in line.split('|')]
        if parts and parts[0] == '':
            parts = parts[1:]
        if parts and parts[-1] == '':
            parts = parts[:-1]
        if parts:
            ws.append(parts)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    filename = f"tablo_markdown_{timestamp}.xlsx"
    filepath = os.path.join(EXCELS_DIR, filename)
    wb.save(filepath)
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    print(f"\n[GK STUDIO V3] Sunucu Başlatıldı -> http://127.0.0.1:{STUDIO_PORT}")
    app.run(host='127.0.0.1', port=STUDIO_PORT, debug=False, threaded=True)
