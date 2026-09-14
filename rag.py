# -*- coding: utf-8 -*-
"""GK STUDIO V3 RAG - multi-encoding text reader + indexing diagnostics."""

import os
import re
from pathlib import Path

from config import CHROMA_DIR, EMBED_MODEL
from backends.ollama_backend import OllamaBackend

CHROMADB_AVAILABLE = False
try:
    import chromadb
    CHROMADB_AVAILABLE = True
except ImportError:
    pass

SKIP_DIRS = {
    ".git", "venv", ".venv", "__pycache__", "node_modules",
    "chat_history", "conversations", "exports", "excel", "uploads",
    "chroma_db", "logs", "GK_Studyo_Exports"
}

SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".zip", ".7z", ".rar",
    ".exe", ".dll", ".bin", ".pyc", ".pyo", ".ico", ".db", ".sqlite", ".sqlite3",
    ".xlsx", ".xls", ".pdf", ".mp3", ".wav", ".mp4", ".avi", ".mov"
}

TEXT_ENCODINGS = [
    "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be",
    "cp1254", "windows-1254", "iso-8859-9", "latin-1"
]


def _chroma_client():
    if not CHROMADB_AVAILABLE:
        return None
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=CHROMA_DIR)


def _safe_collection_name(proj_name):
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", str(proj_name)).strip("_-")
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
        start = max(0, end - overlap)
    return chunks


def _looks_like_utf16(raw):
    if not raw:
        return False
    sample = raw[:4096]
    nul_count = sample.count(b"\x00")
    if nul_count < 8:
        return False
    even_nuls = sum(1 for i in range(0, len(sample), 2) if sample[i] == 0)
    odd_nuls = sum(1 for i in range(1, len(sample), 2) if sample[i] == 0)
    return even_nuls > len(sample) * 0.20 or odd_nuls > len(sample) * 0.20


def _decode_bytes(raw):
    if raw is None:
        return "", "none"
    if not raw:
        return "", "empty"

    if raw.startswith(b"\xef\xbb\xbf"):
        try:
            return raw.decode("utf-8-sig"), "utf-8-sig"
        except Exception:
            pass

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        try:
            return raw.decode("utf-16"), "utf-16"
        except Exception:
            pass

    if _looks_like_utf16(raw):
        for enc in ("utf-16-le", "utf-16-be"):
            try:
                text = raw.decode(enc)
                if text and any(ch.isalpha() for ch in text):
                    return text, enc
            except Exception:
                pass

    for enc in TEXT_ENCODINGS:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception:
            continue

    try:
        return raw.decode("utf-8", errors="replace"), "utf-8-replace"
    except Exception:
        return "", "decode-failed"


def read_text_file(file_path):
    result = {"status": "error", "text": "", "encoding": "", "chars": 0, "bytes": 0}
    path = Path(file_path)
    try:
        raw = path.read_bytes()
    except Exception as exc:
        print(f"[RAG DOSYA HATASI] {path.name} -> {exc}")
        result["encoding"] = "read-error"
        return result

    result["bytes"] = len(raw)
    if not raw:
        result["status"] = "empty"
        result["encoding"] = "empty"
        return result

    if path.suffix.lower() in SKIP_EXTENSIONS:
        result["status"] = "binary"
        result["encoding"] = "skipped-extension"
        return result

    text, encoding = _decode_bytes(raw)
    result["text"] = text
    result["encoding"] = encoding
    result["chars"] = len(text)

    if not text.strip():
        result["status"] = "empty"
        return result

    sample = text[:5000]
    control_chars = 0
    for ch in sample:
        code = ord(ch)
        if code < 9 or 13 < code < 32:
            control_chars += 1
    if len(sample) > 100 and (control_chars / len(sample)) > 0.05:
        result["status"] = "binary"
        result["encoding"] = "binary-like"
        return result

    result["status"] = "ok"
    return result


def _iter_project_files(proj_path):
    root_path = Path(proj_path)
    if not root_path.exists():
        return
    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file_name in files:
            path = Path(root) / file_name
            if path.suffix.lower() in SKIP_EXTENSIONS:
                continue
            yield path


def clear_project_index(proj_name):
    if not CHROMADB_AVAILABLE:
        return
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        try:
            client.delete_collection(coll_name)
            print(f"[RAG TEMIZLIK] '{proj_name}' eski indeks silindi.")
        except Exception:
            pass
    except Exception as exc:
        print(f"[RAG TEMIZLIK HATASI] {proj_name}: {exc}")


def index_project_folder(proj_name, proj_path):
    if not CHROMADB_AVAILABLE:
        return {"status": "error", "message": "chromadb kütüphanesi kurulu değil."}
    if not os.path.exists(proj_path):
        return {"status": "error", "message": f"Proje dizini bulunamadı: {proj_path}"}

    print("\n" + "=" * 78)
    print(f"[RAG INDEKS BASLADI] Proje: {proj_name}")
    print(f"[RAG DIZIN] {proj_path}")
    print("=" * 78)

    client = _chroma_client()
    coll_name = _safe_collection_name(proj_name)
    clear_project_index(proj_name)

    try:
        collection = client.create_collection(coll_name)
    except Exception as exc:
        return {"status": "error", "message": f"Chroma koleksiyonu oluşturulamadı: {exc}"}

    ids, embeddings, documents, metadatas = [], [], [], []
    file_count = 0
    indexed_file_count = 0
    empty_file_count = 0
    error_file_count = 0
    binary_file_count = 0
    chunk_count = 0
    encoding_counts = {}

    for file_path in _iter_project_files(proj_path):
        rel_path = os.path.relpath(str(file_path), str(proj_path))
        info = read_text_file(file_path)
        file_count += 1

        if info["status"] == "empty":
            empty_file_count += 1
            print(f"[RAG DOSYA] EMPTY | {rel_path}")
            continue

        if info["status"] == "binary":
            binary_file_count += 1
            print(f"[RAG DOSYA] SKIP-BINARY | {rel_path}")
            continue

        if info["status"] != "ok":
            error_file_count += 1
            print(f"[RAG DOSYA] ERROR | {rel_path} | encoding={info['encoding']}")
            continue

        indexed_file_count += 1
        encoding = info["encoding"]
        encoding_counts[encoding] = encoding_counts.get(encoding, 0) + 1
        text = info["text"]
        chunks = _chunk_text(text)

        print(
            f"[RAG DOSYA] OK | {rel_path} | "
            f"encoding={encoding} | chars={info['chars']} | chunks={len(chunks)}"
        )

        file_embedding_errors = 0
        for i, chunk in enumerate(chunks):
            try:
                emb = OllamaBackend.get_embedding(chunk)
            except Exception as exc:
                file_embedding_errors += 1
                print(f"[RAG EMBEDDING HATASI] {rel_path} | parca={i} | {exc}")
                continue

            ids.append(f"{rel_path}::{i}")
            embeddings.append(emb)
            documents.append(chunk)
            metadatas.append({"file": rel_path, "chunk": i, "encoding": encoding})
            chunk_count += 1

        if file_embedding_errors:
            error_file_count += 1

    if ids:
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                embeddings=embeddings[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

    print("\n" + "=" * 78)
    print("[RAG INDEKS OZET]")
    print(f"Toplam dosya     : {file_count}")
    print(f"Indekslenen      : {indexed_file_count}")
    print(f"Bos              : {empty_file_count}")
    print(f"Binary/atlanan   : {binary_file_count}")
    print(f"Hata             : {error_file_count}")
    print(f"Toplam chunk     : {chunk_count}")
    print(f"Encoding dagilimi: {encoding_counts}")
    print("=" * 78 + "\n")

    return {
        "status": "success",
        "file_count": indexed_file_count,
        "chunk_count": chunk_count,
        "empty_file_count": empty_file_count,
        "binary_file_count": binary_file_count,
        "error_file_count": error_file_count,
        "encoding_counts": encoding_counts,
    }


def rag_query(proj_name, query, k=5):
    if not CHROMADB_AVAILABLE:
        return None
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        try:
            collection = client.get_collection(coll_name)
        except Exception:
            print(f"[RAG SORGU] Koleksiyon bulunamadı: {proj_name}")
            return None

        search_query = f"search_query: {query}" if "nomic" in EMBED_MODEL.lower() else query
        query_emb = OllamaBackend.get_embedding(search_query)

        results = collection.query(
            query_embeddings=[query_emb],
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            print(f"[RAG SORGU] '{proj_name}' için sonuç yok.")
            return None

        print(f"[RAG SORGU] Proje={proj_name} Sonuc={len(docs)}")

        parts = []
        for idx, (doc, meta) in enumerate(zip(docs, metas), 1):
            file_name = meta.get("file", "?") if meta else "?"
            chunk_num = meta.get("chunk", "?") if meta else "?"
            encoding = meta.get("encoding", "?") if meta else "?"
            dist = distances[idx - 1] if distances and len(distances) >= idx else None
            score = f" | distance={round(dist, 4)}" if dist is not None else ""
            print(f"  [{idx}] {file_name} (chunk={chunk_num}, encoding={encoding}){score}")
            parts.append(f"--- DOSYA: {file_name} (parça {chunk_num}) ---\n{doc}")

        return "[PROJE İÇİNDEN RAG İLE SÜZÜLEN İLGİLİ PARÇALAR]:\n" + "\n\n".join(parts)

    except Exception as exc:
        print(f"[RAG SORGU HATASI] {exc}")
        return None


__all__ = [
    "CHROMADB_AVAILABLE",
    "read_text_file",
    "clear_project_index",
    "index_project_folder",
    "rag_query",
]