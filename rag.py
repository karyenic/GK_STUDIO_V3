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
    return f"p_{safe}"[:63]

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

    for root, dirs, files in os.walk(proj_path):
        dirs[:] = [d for d in dirs if d not in ['.git', 'venv', '__pycache__', 'node_modules', 'chat_history', 'conversations', 'exports', 'excel', 'uploads', 'chroma_db', 'logs', '_backups', 'ARCHIVE', '.gk_studio']]
        for file in files:
            lower_f = file.lower()
            if lower_f.endswith(('.png', '.jpg', '.jpeg', '.zip', '.exe', '.pyc', '.xlsx', '.pdf', '.ico', '.db', '.bak', '.patch')):
                continue
            file_full_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_full_path, proj_path)
            try:
                with open(file_full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue
            if not content.strip():
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

    print(f"[RAG İNDEKS] Proje: {proj_name} | Dosya: {file_count}, Chunk: {len(ids)}")
    return {"status": "success", "file_count": file_count, "chunk_count": len(ids)}

def rag_query(proj_name, query, k=3):
    """
    Sistemi yormayan, doğrudan ve hızlı vektör arama motoru.
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

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=k,
            include=["documents", "metadatas"]
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if not docs:
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