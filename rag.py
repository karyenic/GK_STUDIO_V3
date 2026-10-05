# C:\AI_YEREL\GK_STUDIO_V3\rag.py
# -*- coding: utf-8 -*-
import os
import re
from config import CHROMA_DIR, EMBED_MODEL
from backends.ollama_backend import OllamaBackend

CHROMADB_AVAILABLE = False
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    pass


# ============================================================
# RAG İNDEKSLEME FİLTRESİ (WHITELIST YAKLAŞIMI)
# Sadece işlevsel dosyalar indekslenir. Gürültü, yedek, gizli
# dosyalar ve launcher script'leri dışlanır.
# ============================================================

# İndekslenecek uzantılar (kesin whitelist)
INCLUDE_EXTENSIONS = {
    # Python
    '.py', '.pyw',
    # JavaScript / TypeScript
    '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx',
    # Web
    '.html', '.htm', '.css', '.scss', '.sass', '.less',
    # Yapılandırma
    '.json', '.yaml', '.yml', '.toml',
    # Veritabanı
    '.sql',
}

# Uzantısız ama kritik dosyalar (whitelist bypass)
INCLUDE_FILENAMES = {
    'requirements.txt',
    'package.json',
    'pyproject.toml',
    'dockerfile',
    'makefile',
    'readme.md',
}

# Kesin dışlanan dosya adları (gizli, hassas, meta)
EXCLUDE_FILENAMES = {
    '.env', '.env.local', '.env.production', '.env.development',
    '.gitignore', '.dockerignore',
    'chroma.sqlite3',
    '.gk_project_conversation_migrated',
}

# Dosya adında bu desenlerden biri geçiyorsa dışla (yedek/test)
EXCLUDE_FILENAME_PATTERNS = [
    '_backup', 'backup_',
    '_yedek', 'yedek_',
    '.before_', '_before_',
    '_test', 'test_query',
    '_old', 'old_',
    'ui_js_', 'workspace_js_',
]

# Dışlanan klasör adları (case-insensitive, herhangi bir seviyede)
EXCLUDE_DIRS = {
    # Sürüm kontrol
    '.git', '.svn', '.hg',
    # Bağımlılıklar
    'node_modules', 'bower_components', 'vendor',
    # Sanal ortamlar
    'venv', '.venv', 'env',
    # Python cache
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
    # Build çıktıları
    'dist', 'build', 'out', 'target',
    # Yedekler
    'backups', '_backups',
    'archive',
    # Studio meta
    '.gk_studio',
    'chroma_db', 'conversations', 'chat_history',
    'exports', 'excel', 'uploads', 'logs',
    # Editör
    '.idea', '.vscode', '.vs',
}


def _should_index_file(fname_lower):
    """
    Bir dosyanın indekslenip indekslenmeyeceğine karar verir.
    True → indeksle, False → atla.
    """
    # 1. Kesin dışlananlar
    if fname_lower in EXCLUDE_FILENAMES:
        return False

    # 2. Uzantısız ama kritik dosyalar (whitelist bypass)
    if fname_lower in INCLUDE_FILENAMES:
        return True

    # 3. Yedek/test desenleri
    if any(p in fname_lower for p in EXCLUDE_FILENAME_PATTERNS):
        return False

    # 4. Uzantı kontrolü
    _, ext = os.path.splitext(fname_lower)
    if not ext:
        return False  # uzantısız ve whitelist'te değil → atla
    if ext not in INCLUDE_EXTENSIONS:
        return False

    return True


def _chroma_client():
    if not CHROMADB_AVAILABLE:
        return None
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def _safe_collection_name(proj_name):
    """
    Proje adını temizleyerek her proje için ayrı bir ChromaDB koleksiyonu oluşturur.
    """
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', proj_name or "default").strip('_-')
    return f"proj_{safe}"[:63]


def _chunk_text_smart(text, max_chars=1500, overlap=300):
    if not text:
        return []
    raw_blocks = text.split('\n\n')
    chunks = []
    current_chunk = ""

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if len(block) > max_chars:
            lines = block.split('\n')
            sub_chunk = ""
            for line in lines:
                if len(sub_chunk) + len(line) + 1 <= max_chars:
                    sub_chunk += ("\n" if sub_chunk else "") + line
                else:
                    if sub_chunk:
                        chunks.append(sub_chunk.strip())
                    sub_chunk = line
            if sub_chunk:
                chunks.append(sub_chunk.strip())
        else:
            if len(current_chunk) + len(block) + 2 <= max_chars:
                current_chunk += ("\n\n" if current_chunk else "") + block
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = block

    if current_chunk:
        chunks.append(current_chunk.strip())

    return [c for c in chunks if c]


def clear_project_index(proj_name):
    if not CHROMADB_AVAILABLE:
        return
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        client.delete_collection(coll_name)
        print(f"[RAG TEMİZLİK] '{proj_name}' koleksiyonu silindi.")
    except Exception:
        pass


def index_project_folder(proj_name, proj_path):
    if not CHROMADB_AVAILABLE:
        return {"status": "error", "message": "chromadb kurulu değil."}

    client = _chroma_client()
    coll_name = _safe_collection_name(proj_name)

    clear_project_index(proj_name)
    collection = client.create_collection(coll_name)

    ids, embeddings, documents, metadatas = [], [], [], []
    file_count = 0
    skipped_count = 0

    for root, dirs, files in os.walk(proj_path):
        # ✅ Klasör filtresi (case-insensitive)
        dirs[:] = [d for d in dirs if d.lower() not in EXCLUDE_DIRS]

        for file in files:
            fname_lower = file.lower()

            # ✅ Dosya filtresi (whitelist yaklaşımı)
            if not _should_index_file(fname_lower):
                skipped_count += 1
                continue

            file_full_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_full_path, proj_path)

            # Boyut kontrolü (2 MB üstü dosyaları atla)
            try:
                if os.path.getsize(file_full_path) > 2 * 1024 * 1024:
                    skipped_count += 1
                    continue
            except OSError:
                skipped_count += 1
                continue

            try:
                with open(file_full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                skipped_count += 1
                continue

            if not content.strip():
                skipped_count += 1
                continue

            file_count += 1
            for i, chunk in enumerate(_chunk_text_smart(content)):
                try:
                    emb = OllamaBackend.get_embedding(chunk)
                    if not emb:
                        continue
                    ids.append(f"{rel_path}::{i}")
                    embeddings.append(emb)
                    documents.append(chunk)
                    metadatas.append({"file": rel_path, "chunk": i})
                except Exception:
                    pass

    if ids:
        batch = 50
        for i in range(0, len(ids), batch):
            collection.add(
                ids=ids[i:i+batch],
                embeddings=embeddings[i:i+batch],
                documents=documents[i:i+batch],
                metadatas=metadatas[i:i+batch]
            )

    print(f"[RAG İNDEKS] Proje: {proj_name} | "
          f"Dosya: {file_count} (atlanan: {skipped_count}), Chunk: {len(ids)}")
    return {
        "status": "success",
        "file_count": file_count,
        "chunk_count": len(ids),
        "skipped_count": skipped_count,
    }


def rag_query(proj_name, query, k=5):
    """
    Hibrit arama: %65 vektör + %35 kelime + dosya adı ipucu bonusu.
    - Query'de geçen dosya adları tespit edilir (ör. "rag.py", "gateway.py").
    - Eşleşen dosyalardan gelen chunk'lar +0.4 bonus alır.
    """
    if not CHROMADB_AVAILABLE:
        return None
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        try:
            collection = client.get_collection(coll_name)
        except Exception:
            return None

        search_query = f"search_query: {query}" if "nomic" in EMBED_MODEL.lower() else query
        query_emb = OllamaBackend.get_embedding(search_query)
        if not query_emb:
            return None

        # 1. Geniş havuz çek
        fetch_k = max(k * 3, 15)
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=fetch_k,
            include=["documents", "metadatas", "distances"]
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return None

        # 2. Query'den dosya adı ipuçlarını çıkar
        # Örnek: "rag.py'deki fonksiyon" → {'rag.py'}
        file_hints = set()
        hint_pattern = r'\b([a-zA-Z_][\w\-]*\.(?:py|js|mjs|ts|tsx|jsx|html|htm|css|json|yaml|yml|toml|md|txt|sql))\b'
        for m in re.findall(hint_pattern, query.lower()):
            file_hints.add(m)

        # 3. Hibrit skorlama
        query_tokens = set(re.findall(r'\w+', query.lower()))
        scored = []

        for doc, meta, dist in zip(docs, metas, distances):
            doc_lower = doc.lower()
            file_name = meta.get('file', '').lower()

            # Kelime eşleşme sayısı (dosya adında geçiyorsa 2x bonus)
            keyword_hits = 0
            for token in query_tokens:
                if token in doc_lower:
                    keyword_hits += 1
                    if token in file_name:
                        keyword_hits += 1

            # Vektör skoru normalizasyonu
            vector_score = 1.0 / (1.0 + max(0.0, dist))

            # Kelime skoru normalizasyonu
            keyword_score = min(keyword_hits / max(len(query_tokens), 1), 1.0)

            # ✅ Dosya adı ipucu bonusu
            filename_bonus = 0.0
            for hint in file_hints:
                if hint in file_name:
                    filename_bonus = 0.4
                    break

            # Hibrit: %65 vektör + %35 kelime + dosya adı bonusu
            hybrid_score = (0.65 * vector_score) + (0.35 * keyword_score) + filename_bonus

            scored.append({
                "doc": doc,
                "meta": meta,
                "score": hybrid_score,
                "hint": filename_bonus > 0,
            })

        # 4. Skora göre sırala, ilk k tanesini al
        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:k]

        # 5. Debug log (isteğe bağlı — görmek istersen aç)
        if file_hints:
            print(f"[RAG HINT] query'de dosya adı ipucu: {file_hints} | "
                  f"top-3 dosya: {[t['meta'].get('file','?') for t in top[:3]]}", flush=True)

        # 6. Formatla
        parts = []
        for item in top:
            file_name = item["meta"].get('file', '?')
            chunk_num = item["meta"].get('chunk', '?')
            parts.append(f"--- DOSYA: {file_name} (blok {chunk_num}) ---\n{item['doc']}")

        return "[PROJE İÇİNDEN HİBRİT RAG İLE SÜZÜLEN İLGİLİ BLOKLAR]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None

        # 2. Hibrit skorlama
        query_tokens = set(re.findall(r'\w+', query.lower()))
        scored = []

        for doc, meta, dist in zip(docs, metas, distances):
            doc_lower = doc.lower()
            file_name = meta.get('file', '').lower()

            # Kelime eşleşme sayısı (dosya adında geçiyorsa 2x bonus)
            keyword_hits = 0
            for token in query_tokens:
                if token in doc_lower:
                    keyword_hits += 1
                    if token in file_name:
                        keyword_hits += 1  # dosya adı bonusu

            # Vektör skoru normalizasyonu (küçük mesafe = daha iyi)
            vector_score = 1.0 / (1.0 + max(0.0, dist))

            # Kelime skoru normalizasyonu
            keyword_score = min(keyword_hits / max(len(query_tokens), 1), 1.0)

            # Hibrit: %65 vektör + %35 kelime
            hybrid_score = (0.65 * vector_score) + (0.35 * keyword_score)

            scored.append({
                "doc": doc,
                "meta": meta,
                "score": hybrid_score,
            })

        # 3. Skora göre sırala, ilk k tanesini al
        scored.sort(key=lambda x: x["score"], reverse=True)
        top = scored[:k]

        # 4. Formatla
        parts = []
        for item in top:
            file_name = item["meta"].get('file', '?')
            chunk_num = item["meta"].get('chunk', '?')
            parts.append(f"--- DOSYA: {file_name} (blok {chunk_num}) ---\n{item['doc']}")

        return "[PROJE İÇİNDEN HİBRİT RAG İLE SÜZÜLEN İLGİLİ BLOKLAR]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None

        parts = []
        for idx, (doc, meta) in enumerate(zip(docs, metas), 1):
            file_name = meta.get('file', '?')
            chunk_num = meta.get('chunk', '?')
            parts.append(f"--- DOSYA: {file_name} (blok {chunk_num}) ---\n{doc}")

        return "[PROJE İÇİNDEN RAG BİLGİLERİ]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None