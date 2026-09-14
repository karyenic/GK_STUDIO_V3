# C:\AI_YEREL\GK_STUDIO_V3\gateway.py
# -*- coding: utf-8 -*-
import time
import json
from config import SYSTEM_PROFILE, ROLE_PROMPTS, DEFAULT_LOCAL_MODEL
from models import get_num_ctx, get_installed_ollama_models
from backends.ipex_backend import IPEXBackend
from backends.gemini_backend import GeminiBackend
from rag import rag_query
from websearch import perform_web_search

class AIGateway:
    @staticmethod
    def process_chat_stream(data):
        t_start = time.time()
        
        prompt = data.get("prompt", "")
        model = data.get("model", "auto")
        role = data.get("role", "default")
        history = data.get("history", [])
        images = data.get("images", None)
        file_package = data.get("filePackage", None)
        use_web = data.get("web_search", False)
        is_project = bool(data.get("is_project", False))
        project_name = data.get("project_name", "").strip()

        # 1. Otomatik Model Yönlendirme (Auto Router)
        route_label = "DIRECT"
        selected_model = model
        if not model or model == "auto":
            p_lower = (prompt + " " + str(file_package or "")).lower()
            installed = get_installed_ollama_models()
            if any(k in p_lower for k in ["kod", "python", "javascript", "fonksiyon", "class", "def ", "script", "hata", "sql", "import "]):
                coder_match = [m for m in installed if "coder" in m.lower()]
                selected_model = coder_match[0] if coder_match else DEFAULT_LOCAL_MODEL
                route_label = "AUTO-CODER"
            elif any(k in p_lower for k in ["neden", "nasıl", "mantık", "analiz", "çözümle", "derin"]):
                r1_match = [m for m in installed if "r1" in m.lower() or "deepseek" in m.lower()]
                selected_model = r1_match[0] if r1_match else DEFAULT_LOCAL_MODEL
                route_label = "AUTO-REASONING"
            else:
                selected_model = DEFAULT_LOCAL_MODEL
                route_label = "AUTO-DEFAULT"

        t_routing = round(time.time() - t_start, 3)

        # 2. Web Arama Katmanı
        t_web_start = time.time()
        if use_web:
            web_context = perform_web_search(prompt)
            prompt = f"[CANLI WEB VERİLERİ]:\n{web_context}\n\n[SORGUNUZ]:\n{prompt}"
        t_web = round(time.time() - t_web_start, 3)

        # 3. RAG Vektör Arama Katmanı
        t_rag_start = time.time()
        rag_context = ""
        if is_project and project_name:
            rag_context = rag_query(project_name, prompt, k=3) or ""
        t_rag = round(time.time() - t_rag_start, 3)

        # 4. MANUEL DOSYA/KLASÖR PAKETİ İLE RAG BAĞLAMININ NET AYRIŞTIRILMASI
        context_blocks = []
        
        if file_package:
            context_blocks.append(f"[GEÇİCİ YÜKLENEN DOSYA / KLASÖR PAKETİ]:\n{file_package}")
            
        if rag_context:
            context_blocks.append(f"{rag_context}")

        if context_blocks:
            full_context_text = "\n\n".join(context_blocks)
            hard_cap_chars = 25000
            
            if len(full_context_text) > hard_cap_chars:
                # Sınırdan geriye doğru giderek ilk satır sonunu (\n) bulur
                last_safe_cut = full_context_text.rfind('\n', 0, hard_cap_chars)
                
                # Eğer devasa tek bir satırsa (örn. minified kod), boşluk arar
                if last_safe_cut == -1:
                    last_safe_cut = full_context_text.rfind(' ', 0, hard_cap_chars)
                    # O da yoksa mecbur tam karakterden keser
                    if last_safe_cut == -1:
                        last_safe_cut = hard_cap_chars
                        
                full_context_text = full_context_text[:last_safe_cut] + "\n\n[!! Akıllı Parçalama: Token sınırına ulaşıldı, bağlam metni satır bütünlüğü korunarak kırpıldı !!]"

            prompt_instruction = prompt if prompt else "Yüklenen içerikleri ve RAG bağlamını inceleyip detaylı Türkçe analiz yap."
            prompt = f"{full_context_text}\n\n[KULLANICI TALİMATI]:\n{prompt_instruction}"

        # 5. Sistem Profili ve Rol Entegrasyonu
        role_instruction = ROLE_PROMPTS.get(role, "")
        system_msg = SYSTEM_PROFILE + ("\n[SİSTEM ROLÜ]: " + role_instruction if role_instruction else "")

        # 6. Dinamik Context Hesaplama
        total_input_chars = len(prompt) + sum(len(h.get("content", "")) for h in history)
        num_ctx = get_num_ctx(selected_model, extra_chars=total_input_chars, is_project=is_project)

        yield "data: " + json.dumps({
            "type": "meta", 
            "model": selected_model, 
            "route": route_label,
            "num_ctx": num_ctx
        }) + "\n\n"

        # 7. Model İcra Katmanı
        t_gen_start = time.time()
        first_token = True
        t_first_token = 0.0

        if selected_model.startswith("gemini"):
            stream_gen = GeminiBackend.generate_stream(prompt, system_instruction=system_msg, images=images)
        else:
            full_prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n"
            valid_history = [h for h in history if h.get('role') in ['user', 'assistant']]
            for h in valid_history[-6:]:
                full_prompt += f"<|im_start|>{h.get('role', 'user')}\n{h.get('content', '')}<|im_end|>\n"
            full_prompt += f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"
            
            stream_gen = IPEXBackend.generate_stream(full_prompt, num_ctx=num_ctx)

        for content, done in stream_gen:
            if first_token and content:
                t_first_token = round(time.time() - t_gen_start, 3)
                first_token = False

            if content:
                yield "data: " + json.dumps({"type": "chunk", "text": content}) + "\n\n"

            if done:
                break

        t_total = round(time.time() - t_start, 2)
        print(f"\n[PERF TELEMETRİ] Model: {selected_model} [{route_label}] | Total: {t_total}s | TTFT: {t_first_token}s | Context: {num_ctx}")

        yield "data: " + json.dumps({
            "type": "done", 
            "elapsed_time": t_total,
            "perf": {
                "ttft": t_first_token,
                "routing": t_routing,
                "rag": t_rag,
                "web": t_web
            }
        }) + "\n\n"
