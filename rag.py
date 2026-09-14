# C:\AI_YEREL\GK_STUDIO_V3\rag.py
# -*- coding: utf-8 -*-
import os
import re
import json
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
    safe = re.sub(r'[^a-zA-Z0-9_-]', '_', proj_name).strip('_-')
    safe = "proj_" + safe if safe else "proj_default"
    return safe[:63]

def _chunk_text(text, chunk_size=900, overlap=150):
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + chunk_size, n)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap
    return chunks

def clear_project_index(proj_name):
    """Proje silindiğinde veya yeniden eklendiğinde eski Vektör DB hafızasını temizler."""
    if not CHROMADB_AVAILABLE:
        return
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        client.delete_collection(coll_name)
        print(f"[RAG TEMİZLİK] '{proj_name}' eski indeks önbelleği silindi.")
    except Exception:
        pass

def index_project_folder(proj_name, proj_path):
    """Proje klasörünü tarar, parçalar ve Port 11435 üzerinden ChromaDB'ye indeksler."""
    if not CHROMADB_AVAILABLE:
        return {"status": "error", "message": "chromadb kütüphanesi kurulu değil."}

    client = _chroma_client()
    coll_name = _safe_collection_name(proj_name)

    clear_project_index(proj_name)
    collection = client.create_collection(coll_name)

    ids, embeddings, documents, metadatas = [], [], [], []
    file_count = 0

    for root, dirs, files in os.walk(proj_path):
        dirs[:] = [d for d in dirs if d not in ['.git', 'venv', '__pycache__', 'node_modules', 'chat_history', 'conversations', 'exports', 'excel', 'uploads', 'chroma_db', 'logs']]
        for file in files:
            lower_f = file.lower()
            if lower_f.endswith(('.png', '.jpg', '.jpeg', '.zip', '.exe', '.pyc', '.xlsx', '.pdf', '.ico', '.db')):
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
            for i, chunk in enumerate(_chunk_text(content)):
                try:
                    emb = OllamaBackend.get_embedding(chunk)
                    ids.append(f"{rel_path}::{i}")
                    embeddings.append(emb)
                    documents.append(chunk)
                    metadatas.append({"file": rel_path, "chunk": i})
                except Exception as e:
                    return {"status": "error", "message": f"Embedding hatası ({rel_path}): {e}"}

    if ids:
        batch = 100
        for i in range(0, len(ids), batch):
            collection.add(
                ids=ids[i:i+batch],
                embeddings=embeddings[i:i+batch],
                documents=documents[i:i+batch],
                metadatas=metadatas[i:i+batch]
            )

    return {"status": "success", "file_count": file_count, "chunk_count": len(ids)}

def rag_query(proj_name, query, k=3):
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

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=k,
            include=["documents", "metadatas", "distances"]
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]

        if not docs:
            return None

        parts = []
        for idx, (doc, meta) in enumerate(zip(docs, metas), 1):
            file_name = meta.get('file', '?')
            chunk_num = meta.get('chunk', '?')
            parts.append(f"--- DOSYA: {file_name} (parça {chunk_num}) ---\n{doc}")

        return "[PROJE İÇİNDEN RAG İLE SÜZÜLEN İLGİLİ PARÇALAR]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None