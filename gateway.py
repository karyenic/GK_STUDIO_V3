# C:\AI_YEREL\GK_STUDIO_V3\gateway.py
# -*- coding: utf-8 -*-
import os
import time
import json
from config import (
    SYSTEM_PROFILE,
    ROLE_PROMPTS,
    DEFAULT_LOCAL_MODEL,
    VISION_MASTER_PROMPT,
    CODER_MASTER_PROMPT,
)
from models import get_num_ctx, get_installed_ollama_models
from backends.ipex_backend import IPEXBackend
from backends.gemini_backend import GeminiBackend
from backends.ollama_backend import OllamaVisionBackend
from rag import rag_query
from websearch import perform_web_search


def get_project_file_tree(base_dir="."):
    """Proje klasöründeki kod dosyalarını tarayıp kompakt bir harita çıkarır."""
    allowed_exts = ('.py', '.js', '.html', '.css')
    tree_lines = []

    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if d not in ['.git', '__pycache__', 'venv', 'env', 'node_modules']]
        for file in files:
            if file.endswith(allowed_exts):
                rel_path = os.path.relpath(os.path.join(root, file), base_dir)
                tree_lines.append(f"📂 {rel_path}")

    return "\n".join(tree_lines)


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
        web_target = str(data.get("web_target", "") or "").strip()
        web_session_context = str(data.get("web_session_context", "") or "")
        is_project = bool(data.get("is_project", False))
        project_name = data.get("project_name", "").strip()

        print(f"\n[REQ] model={model!r} role={role!r} images={len(images) if images else 0} "
              f"pkg_chars={len(file_package) if file_package else 0} "
              f"prompt_len={len(prompt)}", flush=True)

        # ============================================================
        # 1. OTOMATİK MODEL YÖNLENDİRME (Auto Router)
        # ============================================================
        route_label = "DIRECT"
        selected_model = model
        is_coder_request = False
        is_vision_request = bool(images and len(images) > 0)

        if not model or model == "auto":
            if is_vision_request:
                selected_model = "granite3.2-vision:2b"
                route_label = "AUTO-VISION"
            else:
                p_lower = (prompt + " " + str(file_package or "")).lower()
                installed = get_installed_ollama_models()

                if any(k in p_lower for k in [
                    "kod", "python", "javascript", "fonksiyon", "class",
                    "def ", "script", "hata", "sql", "import "
                ]):
                    coder_match = [m for m in installed if "coder" in m.lower()]
                    selected_model = coder_match[0] if coder_match else DEFAULT_LOCAL_MODEL
                    route_label = "AUTO-CODER"
                    is_coder_request = True

                elif any(k in p_lower for k in [
                    "neden", "nasıl", "mantık", "analiz", "çözümle", "derin"
                ]):
                    r1_match = [m for m in installed if "r1" in m.lower() or "deepseek" in m.lower()]
                    selected_model = r1_match[0] if r1_match else DEFAULT_LOCAL_MODEL
                    route_label = "AUTO-REASONING"

                else:
                    selected_model = DEFAULT_LOCAL_MODEL
                    route_label = "AUTO-DEFAULT"

        # ✅ Manuel coder modeli seçimi de coder modunu tetiklesin
        if selected_model and (
            "coder" in selected_model.lower()
            or "deepseek-coder" in selected_model.lower()
            or "codellama" in selected_model.lower()
            or "starcoder" in selected_model.lower()
        ):
            is_coder_request = True
            if route_label == "DIRECT":
                route_label = "MANUAL-CODER"

        t_routing = round(time.time() - t_start, 3)

        # ============================================================
        # 2. WEB ARAMA KATMANI
        # ============================================================
        t_web_start = time.time()
        if use_web:
            web_context = perform_web_search(
                prompt,
                target_url=web_target,
                session_context=web_session_context,
            )
            prompt = f"[CANLI WEB VERİLERİ]:\n{web_context}\n\n[SORGUNUZ]:\n{prompt}"
        t_web = round(time.time() - t_web_start, 3)

        # ============================================================
        # 3. RAG VEKTÖR ARAMA VE PROJE HARİTASI KATMANI
        # ============================================================
        t_rag_start = time.time()
        rag_context = ""
        project_tree = ""

        if is_project:
            # ✅ DÜZELTME: proje yolu varsa onu kullan, yoksa cwd'ye düş
            scan_dir = project_name if project_name and os.path.isdir(project_name) else "."
            project_tree = get_project_file_tree(scan_dir)
            if project_name:
                rag_context = rag_query(project_name, prompt, k=3) or ""
        t_rag = round(time.time() - t_rag_start, 3)

        # ✅ YENİ: RAG debug log (davranışı değiştirmez, sadece görünürlük)
        print(f"[RAG] proje={project_name!r} | "
              f"tree_lines={len(project_tree.splitlines()) if project_tree else 0} | "
              f"rag_chars={len(rag_context)} | t={t_rag}s", flush=True)

        # ============================================================
        # 4. MANUEL DOSYA, PROJE HARİTASI VE RAG BAĞLAMININ BİRLEŞTİRİLMESİ
        # ============================================================
        context_blocks = []

        if project_tree:
            context_blocks.append(f"[PROJE DOSYA HARİTASI]:\n{project_tree}")

        if file_package:
            context_blocks.append(f"[GEÇİCİ YÜKLENEN DOSYA / KLASÖR PAKETİ]:\n{file_package}")

        if rag_context:
            context_blocks.append(f"{rag_context}")

        has_context = False
        if context_blocks:
            has_context = True
            full_context_text = "\n\n".join(context_blocks)
            hard_cap_chars = 25000

            if len(full_context_text) > hard_cap_chars:
                last_safe_cut = full_context_text.rfind('\n', 0, hard_cap_chars)
                if last_safe_cut == -1:
                    last_safe_cut = full_context_text.rfind(' ', 0, hard_cap_chars)
                    if last_safe_cut == -1:
                        last_safe_cut = hard_cap_chars

                full_context_text = (
                    full_context_text[:last_safe_cut]
                    + "\n\n[!! Akıllı Parçalama: Token sınırına ulaşıldı, "
                    "bağlam satır bütünlüğü korunarak kırpıldı !!]"
                )

            prompt_instruction = prompt if prompt else (
                "Yüklenen içerikleri ve proje haritasını inceleyip detaylı Türkçe analiz yap."
            )
            prompt = f"{full_context_text}\n\n[KULLANICI TALİMATI]:\n{prompt_instruction}"

        # ============================================================
        # 5. SİSTEM PROFİLİ, ROL ENTEGRASYONU VE MASTER PROMPT ANAYASASI
        # ============================================================
        role_instruction = ROLE_PROMPTS.get(role, "")
        system_msg = SYSTEM_PROFILE + ("\n[SİSTEM ROLÜ]: " + role_instruction if role_instruction else "")

        if use_web:
            web_constitution = (
                "\n\n[SYSTEM_ROLE: WEB_RESEARCH_GUARD]\n"
                "Web arastirma paketi kanit dosyasi gibi ele alin.\n"
                "1. Sadece [WEB ARASTIRMA RAPORU], [WEB KAYNAK URL'LERİ] ve "
                "[WEB GUARD] içinde bulunan verilere dayan.\n"
                "2. Kullanici bir adet/siralama istediyse, kanit sayisi yetersizse "
                "eksik kayitlar uydurma; eksigi acikca belirt.\n"
                "3. Kaynak URL'si olmayan spesifik sayi, tarih, adet, ciro veya "
                "pazar payini dogrulanmis web verisi gibi sunma.\n"
                "4. Web arastirma metni ile kendi genel bilgisini karistirma; "
                "genel bilgi kullanmak gerekiyorsa bunu acikca ayir.\n"
                "5. Kaynaklar celisiyorsa tek bir degeri secip digerini yok sayma; "
                "celiskiyi kaynaklariyla belirt.\n"
                "6. Excel/tablo talebinde yalnizca kanitlanmis satirlari kullan; "
                "eksik alanlari 'Veri bulunamadi' olarak isaretle."
            )
            system_msg += web_constitution

        if is_coder_request:
            system_msg = CODER_MASTER_PROMPT + "\n\n" + system_msg

        if has_context or is_project:
            strict_coder_constitution = (
                "\n\n[PROJE BAĞLAMI AKTİF]\n"
                "Sana proje dosya haritası ve/veya RAG içeriği sunuldu. "
                "Şu ek kurallar geçerlidir:\n"
                "1. Değişiklik önerdiğinde hangi dosyaya dokunduğunu açıkça belirt "
                "(dosya adı ve yol).\n"
                "2. Proje haritasında görünmeyen bir dosyaya atıf yapma.\n"
                "3. RAG'da gösterilen kod satırlarına dayanarak konuş; "
                "bağlamda olmayan satırları 'mevcut' gibi gösterme."
            )
            system_msg += strict_coder_constitution

        # ============================================================
        # 6. DİNAMİK CONTEXT HESAPLAMA
        # ============================================================
        total_input_chars = len(prompt) + sum(len(h.get("content", "")) for h in history)
        num_ctx = get_num_ctx(
            selected_model,
            extra_chars=total_input_chars,
            is_project=is_project,
            is_vision=is_vision_request,
        )

        print(f"[CTX] {selected_model} → num_ctx={num_ctx} "
              f"(system: {len(system_msg)} char, prompt: {len(prompt)} char, "
              f"route: {route_label}, coder: {is_coder_request}, vision: {is_vision_request})",
              flush=True)

        yield "data: " + json.dumps({
            "type": "meta",
            "model": selected_model,
            "route": route_label,
            "num_ctx": num_ctx,
            "vision": is_vision_request,
            "coder": is_coder_request,
        }) + "\n\n"

        # ============================================================
        # 7. MODEL İCRA KATMANI
        # ============================================================
        t_gen_start = time.time()
        first_token = True
        t_first_token = 0.0

        if selected_model.startswith("gemini"):
            print(f"[ROUTE] → Gemini backend", flush=True)
            stream_gen = GeminiBackend.generate_stream(
                prompt,
                system_instruction=system_msg,
                images=images
            )

        elif is_vision_request:
            print(f"[VISION] {len(images)} görsel → {selected_model}", flush=True)

            role_extra = ROLE_PROMPTS.get(role, "") if role and role != "default" else ""

            p_low = prompt.lower()
            extra_focus = ""
            if any(k in p_low for k in ["oku", "yazı", "metin", "harf"]):
                extra_focus = "\n\n[ODAK: OCR] Sadece net okunabilen metni aktar, uydurma."
            elif any(k in p_low for k in ["kaç", "sayı", "adet", "tane"]):
                extra_focus = "\n\n[ODAK: SAYMA] Önce net sayıyı ver, sonra kısaca açıkla."
            elif any(k in p_low for k in ["fark", "karşılaştır", "vs", "ile"]):
                extra_focus = "\n\n[ODAK: KARŞILAŞTIRMA] Ortak ve farklı yönleri madde madde ayır."
            elif any(k in p_low for k in ["renk", "boyut", "şekil"]):
                extra_focus = "\n\n[ODAK: NİTELİK] Renk, boyut ve şekil bilgilerini net ver."

            vision_prompt = VISION_MASTER_PROMPT + extra_focus
            if role_extra:
                vision_prompt += f"\n\n[EK ROL]: {role_extra}"
            vision_prompt += f"\n\n[KULLANICI SORUSU]:\n{prompt}"

            stream_gen = OllamaVisionBackend.generate_stream(
                model=selected_model,
                prompt=vision_prompt,
                images=images,
                num_ctx=num_ctx
            )

        else:
            # Normal metin sohbeti → IPEX
            full_prompt = f"<|im_start|>system\n{system_msg}<|im_end|>\n"
            valid_history = [h for h in history if h.get('role') in ['user', 'assistant']]
            for h in valid_history[-6:]:
                full_prompt += f"<|im_start|>{h.get('role', 'user')}\n{h.get('content', '')}<|im_end|>\n"
            full_prompt += f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n"

            print(f"[IPEX] prompt gönderiliyor ({len(full_prompt)} char, num_ctx={num_ctx})", flush=True)
            stream_gen = IPEXBackend.generate_stream(full_prompt, num_ctx=num_ctx)

        # ============================================================
        # 8. STREAM DÖNGÜSÜ + CHUNK SAYACI
        # ============================================================
        chunk_count = 0
        for content, done in stream_gen:
            if first_token and content:
                t_first_token = round(time.time() - t_gen_start, 3)
                first_token = False

            if content:
                chunk_count += 1
                yield "data: " + json.dumps({"type": "chunk", "text": content}) + "\n\n"

            if done:
                break

        print(f"[STREAM] Toplam {chunk_count} chunk gönderildi", flush=True)

        t_total = round(time.time() - t_start, 2)
        print(
            f"[PERF TELEMETRİ] Model: {selected_model} [{route_label}] | "
            f"Total: {t_total}s | TTFT: {t_first_token}s | Context: {num_ctx} | Chunks: {chunk_count}",
            flush=True
        )

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