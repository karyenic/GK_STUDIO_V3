# GK STUDIO V3 - RAG STABLE BASELINE ARCHIVE
# Bu betik mevcut RAG'i DEGISTIRMEZ.
# Gonderilen kararlı rag.py dosyasini arsiv/reference olarak proje disina degil,
# proje icinde aktif olmayan bir arsiv klasorune kaydeder.

$ErrorActionPreference = 'Stop'
$Project = 'C:\AI_YEREL\GK_STUDIO_V3'
$Archive = Join-Path $Project 'ARCHIVE\RAG_BASELINES\20260915_STABLE_BASELINE'
$RagFile = Join-Path $Archive 'rag_stable_baseline.py'
$NoteFile = Join-Path $Archive 'README_RAG_STABLE_BASELINE.md'

if (-not (Test-Path -LiteralPath $Project)) {
    throw "Proje klasoru bulunamadi: $Project"
}

New-Item -ItemType Directory -Force -Path $Archive | Out-Null

$rag = @'
# -*- coding: utf-8 -*-
# RAG STABLE BASELINE - REFERANS ONLY
# Kaynak: kullanicinin 15.09.2026 tarihinde paylastigi kararlilik referansi.
# Bu dosya AKTIF RAG olarak calistirilmak uzere degildir.
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
    """Proje silindiğinde veya yeniden eklendiğinde eski Vektor DB hafizasini temizler."""
    if not CHROMADB_AVAILABLE:
        return
    try:
        client = _chroma_client()
        coll_name = _safe_collection_name(proj_name)
        client.delete_collection(coll_name)
        print(f"[RAG TEMIZLIK] '{proj_name}' eski indeks onbellegi silindi.")
    except Exception:
        pass

def index_project_folder(proj_name, proj_path):
    """Proje klasorunu tarar, parcalar ve Port 11435 uzerinden ChromaDB'ye indeksler."""
    if not CHROMADB_AVAILABLE:
        return {"status": "error", "message": "chromadb kutuphanesi kurulu degil."}

    client = _chroma_client()
    coll_name = _safe_collection_name(proj_name)

    try:
        client.delete_collection(coll_name)
        print(f"[RAG] '{proj_name}' eski indeks silindi, yeniden olusturuluyor.")
    except Exception:
        pass

    try:
        collection = client.create_collection(coll_name)
    except Exception:
        collection = client.get_or_create_collection(coll_name)
        try:
            existing = collection.get()
            if existing and existing.get("ids"):
                collection.delete(ids=existing["ids"])
        except Exception as e:
            print(f"[RAG UYARI] Eski kayitlar temizlenemedi: {e}")

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
                    return {"status": "error", "message": f"Embedding hatasi ({rel_path}): {e}"}

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
            parts.append(f"--- DOSYA: {file_name} (parca {chunk_num}) ---\n{doc}")

        return "[PROJE ICINDEN RAG ILE SUZULEN ILGILI PARCALAR]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None
'@

$note = @'
# GK STUDIO V3 - RAG STABLE BASELINE

Tarih: 15.09.2026
Durum: REFERANS / ARSIV
Aktif V3 RAG: HAYIR

## Bu dosya neden burada?

Kullanicinin 15.09.2026 tarihinde paylastigi RAG surumu, mevcut V3 davranislarina gore daha kararlı bir temel olarak degerlendirildi.
Bu nedenle aktif `rag.py` yerine gecmez. Yalnizca sonraki gelistirmelerde karsilastirma ve geri donus referansi olarak saklanir.

## Onemli kural

Bu klasor aktif uygulama tarafindan import edilmemelidir.
Aktif `C:\AI_YEREL\GK_STUDIO_V3\rag.py` dosyasi DEGISTIRILMEMISTIR.

## Bilinen ozellikler

- `os.walk()` ile proje dizinini tarar.
- Belirli klasorleri tarama disinda birakir.
- Metin dosyalarini UTF-8 `errors='ignore'` ile okur.
- Chunk boyutu 900, overlap 150'dir.
- Embedding `OllamaBackend.get_embedding()` ile alinir.
- ChromaDB PersistentClient kullanilir.
- Proje collection'i yeniden indekslemede temizlenir.
- Metadata olarak `file` ve `chunk` tutulur.
- RAG sorgusu varsayilan olarak `k=3` kullanir.
- PDF/XLSX gibi bazi ikili formatlari dogrudan okumaz.

## Neden baseline olarak saklandi?

Kullanici bu surumu daha kararli ve daha tutarli buldu.
Sonraki calismalarda once mevcut V3 ile bu baseline arasindaki farklar tespit edilecek.
Kod degisikligi yapmadan once bu dosya referans alinacak.

## Sonraki hedefler

1. Dizin taramasinin eksik dosya birakip birakmadigini kanitlamak.
2. Encoding sorunlarini kontrollu bicimde duzeltmek.
3. RAG'in olmayan dosya veya icerik uydurmasini onlemek.
4. Retrieval kalitesini artirmak.
5. Master Prompt + Skill Injection katmanini RAG'dan ayri tasarlamak.

## GERI DONUS NOTU

Bu dosya bir 'calisan yeni surum' degildir.
Bu, 15.09.2026 tarihli kararli referans kopyasidir.
Aktif etmek icin yeni sohbette ayrica karar verilmelidir.
'@

[System.IO.File]::WriteAllText($RagFile, $rag, (New-Object System.Text.UTF8Encoding($false)))
[System.IO.File]::WriteAllText($NoteFile, $note, (New-Object System.Text.UTF8Encoding($false)))

Write-Host "" 
Write-Host "RAG baseline arsivlendi." -ForegroundColor Green
Write-Host "" 
Write-Host "RAG : $RagFile"
Write-Host "NOT : $NoteFile"
Write-Host "" 
Write-Host "AKTIF rag.py degistirilmedi." -ForegroundColor Cyan
