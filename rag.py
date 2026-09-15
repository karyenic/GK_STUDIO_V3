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

    # ONEMLI DUZELTME: clear_project_index() KENDI AYRI client'ini olusturup
    # silme yapiyordu, ardindan create_collection BASKA bir client uzerinden
    # cagriliyordu. ChromaDB'de bu, silmenin henuz yansimadigi bir ara
    # duruma ve "collection already exists" hatasina yol acabiliyor -
    # "ilk indeksleme hatasi"nin muhtemel sebebi buydu. Artik AYNI client
    # uzerinden, get_or_create + guvenli silme ile ilerliyoruz.
    try:
        client.delete_collection(coll_name)
        print(f"[RAG] '{proj_name}' eski indeks silindi, yeniden oluşturuluyor.")
    except Exception:
        pass  # koleksiyon yoksa sorun degil - ilk indeksleme normal durum

    try:
        collection = client.create_collection(coll_name, metadata={"hnsw:space": "cosine"})
    except Exception:
        # Silme bir sekilde yansimadiysa mevcut olani al ve icini bosalt
        collection = client.get_or_create_collection(coll_name, metadata={"hnsw:space": "cosine"})
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

def rag_query(proj_name, query, k=5):
    """ONEMLI DUZELTME: onceden mesafe/benzerlik skoru (distances) chroma'dan
    cekiliyordu ama HIC KULLANILMIYORDU - soru dizindeki hicbir seyle iyi
    eslesmese bile "en yakin 3 parca" ne olursa olsun modele veriliyordu.
    Model de bunlari gercek bir eslesme sanip, bazen parcalarin icindeki
    baska dosya adlarindan esinlenerek OLMAYAN dosyalar uyduruyordu.
    Artik: (1) cosine mesafesi bir esigin (RAG_DISTANCE_THRESHOLD) UZERINDE
    olan zayif eslesmeler ATILIYOR, (2) modele SADECE gercekten bulunan
    dosya adlarinin listesi + bunlarin disina cikmamasi icin ACIK bir
    disiplin talimati veriliyor, (3) hicbir sey esik altinda kalmazsa
    (yani gercekten alakali icerik yoksa) model 'bulamadim' demeye
    ZORLANIYOR, sessizce halusinasyon yapmasi engelleniyor."""
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

        # k'yi biraz genis tutup esikten sonra elenenleri disariya at -
        # boylece esik sonrasi elimizde hala yeterli parca kalma sansi artar.
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=max(k * 2, 8),
            include=["documents", "metadatas", "distances"]
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        if not docs:
            return ("[RAG UYARISI: Bu proje için hiçbir indeks kaydı bulunamadı. "
                    "Kullanıcıya bunu açıkça söyle, dosya adı veya içerik uydurma.]")

        # cosine mesafesi: 0 = birebir ayni, 2 = tamamen alakasiz.
        # 0.55 pratikte "makul alakali" ile "zayif/tesadufi" arasindaki
        # sinira yakin bir deger - kesin bilim degil, ampirik bir baslangic.
        RAG_DISTANCE_THRESHOLD = 0.55
        filtered = [(doc, meta, dist) for doc, meta, dist in zip(docs, metas, dists) if dist <= RAG_DISTANCE_THRESHOLD]
        filtered = filtered[:k]

        print(f"[RAG] Sorgu: '{query[:60]}...' | Ham mesafeler: {[round(d,3) for d in dists]} | Eşik sonrası kalan: {len(filtered)}/{len(docs)}")

        if not filtered:
            return (f"[RAG UYARISI: '{query[:80]}' sorgusu için dizinde yeterince alakalı içerik "
                     f"bulunamadı (en yakın eşleşme bile çok zayıftı). Kullanıcıya bunu açıkça söyle - "
                     f"'bu konuda dizinde bir şey bulamadım' de. ASLA dosya adı veya içerik uydurma. "
                     f"Kullanıcıdan dosya adını netleştirmesini veya farklı kelimelerle sormasını iste.]")

        found_files = sorted(set(meta.get('file', '?') for _, meta, _ in filtered))
        parts = []
        for doc, meta, dist in filtered:
            file_name = meta.get('file', '?')
            chunk_num = meta.get('chunk', '?')
            parts.append(f"--- DOSYA: {file_name} (parça {chunk_num}, benzerlik mesafesi: {round(dist,3)}) ---\n{doc}")

        discipline = (
            "[RAG DİSİPLİN KURALI - KESİNLİKLE UYULACAK]:\n"
            f"Aşağıdaki parçalar SADECE şu gerçek dosyalardan geliyor: {', '.join(found_files)}.\n"
            "1) Bu listenin DIŞINDA bir dosya adından ASLA bahsetme - listelenmemiş bir dosya "
            "'muhtemelen vardır' diye tahmin etme veya uydurma.\n"
            "2) Aşağıdaki parçalar sorunun TAMAMINI cevaplamıyorsa, bunu açıkça söyle - eksik "
            "kısmı kendi bilginle/tahminle doldurma.\n"
            "3) Emin olmadığın her şey için 'bu bilgi verilen parçalarda yok' de, asla icat etme.\n"
        )
        return discipline + "\n[PROJE İÇİNDEN RAG İLE SÜZÜLEN İLGİLİ PARÇALAR]:\n" + "\n\n".join(parts)
    except Exception as e:
        print(f"[RAG SORGU HATASI]: {e}")
        return None