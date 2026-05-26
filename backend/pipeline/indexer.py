"""
pipeline/indexer.py

Persistent hybrid index: FAISS HNSW (dense) + BM25Okapi (sparse).

The index itself. Manages four things in memory and on disk:

FAISS HNSW index for dense vector search
Global BM25 index for sparse keyword search
Per-doc BM25 dict (one BM25 index per PDF using only that PDF's vocabulary)
MD5 hash set for dedup
"""

import faiss
import numpy as np
import pickle
import hashlib
import os
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from config import (
    EMBED_MODEL_NAME,
    HNSW_NEIGHBORS,
    HNSW_EF_CONSTRUCTION,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    BM25_PATH,
    DEDUP_COSINE_THRESHOLD,
)

print("Loading embedding model...")
embed_model = SentenceTransformer(EMBED_MODEL_NAME)
print("Embedding model loaded!")

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------
documents: list[dict] = []
texts: list[str] = []
index: faiss.Index | None = None
bm25: BM25Okapi | None = None
per_doc_bm25: dict[str, BM25Okapi] = {}
chunk_hashes: set[str] = set()          # MD5 hashes of all indexed chunk texts


# ---------------------------------------------------------------------------
# Deduplication helpers
# ---------------------------------------------------------------------------

def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _filter_exact_duplicates(new_docs: list[dict]) -> list[dict]:
    """
    Remove chunks whose MD5 hash already exists in chunk_hashes.
    Updates chunk_hashes with hashes of surviving docs.
    """
    survivors = []
    for doc in new_docs:
        h = _md5(doc["text"])
        if h in chunk_hashes:
            print(f"    Exact duplicate skipped: {doc['text'][:60]!r}")
        else:
            chunk_hashes.add(h)
            survivors.append(doc)
    return survivors


def _filter_near_duplicates(new_docs: list[dict], new_embeddings: np.ndarray) -> tuple[list[dict], np.ndarray]:
    """
    Remove chunks whose cosine similarity to any existing FAISS vector
    is >= DEDUP_COSINE_THRESHOLD.

    Uses FAISS inner-product search on L2-normalised vectors (= cosine sim).
    Only runs when an existing index is present (no existing index means
    no duplicates possible yet).

    Returns (surviving_docs, surviving_embeddings).
    """
    if index is None or index.ntotal == 0 or len(new_docs) == 0:
        return new_docs, new_embeddings

    # L2-normalise for cosine similarity via inner product
    norms = np.linalg.norm(new_embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-10, norms)
    normed = new_embeddings / norms

    # Search for closest existing vector for each new chunk
    D, _ = index.search(normed.astype(np.float32), 1)

    survivors_idx = []
    for i, sim in enumerate(D[:, 0]):
        if sim >= DEDUP_COSINE_THRESHOLD:
            print(f"    Near-duplicate skipped (sim={sim:.3f}): {new_docs[i]['text'][:60]!r}")
        else:
            survivors_idx.append(i)

    if not survivors_idx:
        return [], np.empty((0, new_embeddings.shape[1]), dtype=np.float32)

    surviving_docs = [new_docs[i] for i in survivors_idx]
    surviving_embeddings = new_embeddings[survivors_idx]
    return surviving_docs, surviving_embeddings


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _save_state():
    if index is not None:
        faiss.write_index(index, FAISS_INDEX_PATH)
    with open(METADATA_PATH, "wb") as f:
        pickle.dump({"documents": documents, "texts": texts, "chunk_hashes": chunk_hashes}, f)
    with open(BM25_PATH, "wb") as f:
        pickle.dump({"global": bm25, "per_doc": per_doc_bm25}, f)


def load_state():
    global documents, texts, index, bm25, per_doc_bm25, chunk_hashes

    if not os.path.exists(FAISS_INDEX_PATH) or not os.path.exists(METADATA_PATH):
        return False

    try:
        index = faiss.read_index(FAISS_INDEX_PATH)
        with open(METADATA_PATH, "rb") as f:
            state = pickle.load(f)
        documents = state["documents"]
        texts = state["texts"]
        # chunk_hashes may be absent in older pickles - rebuild from texts
        if "chunk_hashes" in state:
            chunk_hashes = state["chunk_hashes"]
        else:
            chunk_hashes = {_md5(t) for t in texts}

        if os.path.exists(BM25_PATH):
            with open(BM25_PATH, "rb") as f:
                bm25_state = pickle.load(f)
            if isinstance(bm25_state, dict) and "global" in bm25_state:
                bm25 = bm25_state["global"]
                per_doc_bm25 = bm25_state.get("per_doc", {})
            else:
                bm25 = bm25_state
                per_doc_bm25 = {}
                _rebuild_per_doc_bm25()
        else:
            _rebuild_bm25()
            _rebuild_per_doc_bm25()

        print(f"Loaded {len(documents)} chunks from disk ({len(per_doc_bm25)} PDFs). "
              f"{len(chunk_hashes)} hashes in dedup cache.")
        return True
    except Exception as e:
        print(f"Warning: could not load persisted index ({e}). Starting fresh.")
        return False


# ---------------------------------------------------------------------------
# Index construction helpers
# ---------------------------------------------------------------------------

def _build_faiss_from_embeddings(embeddings: np.ndarray) -> faiss.Index:
    dimension = embeddings.shape[1]
    idx = faiss.IndexHNSWFlat(dimension, HNSW_NEIGHBORS)
    idx.hnsw.efConstruction = HNSW_EF_CONSTRUCTION
    idx.add(embeddings)
    return idx


def _rebuild_bm25():
    global bm25
    tokenized = [t.split() for t in texts]
    bm25 = BM25Okapi(tokenized) if tokenized else None


def _rebuild_per_doc_bm25():
    global per_doc_bm25
    per_doc_bm25 = {}
    doc_texts: dict[str, list[str]] = {}
    for doc in documents:
        did = doc.get("metadata", {}).get("doc_id", "unknown")
        doc_texts.setdefault(did, []).append(doc["text"])
    for did, dtexts in doc_texts.items():
        tokenized = [t.split() for t in dtexts]
        per_doc_bm25[did] = BM25Okapi(tokenized)


def _add_to_per_doc_bm25(doc_id: str, new_docs: list[dict]):
    global per_doc_bm25
    existing = [doc["text"] for doc in documents if doc.get("metadata", {}).get("doc_id") == doc_id]
    new_texts = [doc["text"] for doc in new_docs]
    all_texts = existing + new_texts
    tokenized = [t.split() for t in all_texts]
    per_doc_bm25[doc_id] = BM25Okapi(tokenized)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index(docs: list[dict]):
    """Legacy / first-upload path - prefer add_to_index() for incremental adds."""
    global documents, texts, index, bm25, chunk_hashes

    docs = _filter_exact_duplicates(docs)
    if not docs:
        print("All chunks were exact duplicates - nothing to index.")
        return

    documents = docs
    texts = [doc["text"] for doc in documents]

    print("Encoding documents...")
    embeddings = embed_model.encode(texts, show_progress_bar=True, batch_size=16)
    embeddings = np.array(embeddings, dtype=np.float32)

    index = _build_faiss_from_embeddings(embeddings)
    _rebuild_bm25()
    _rebuild_per_doc_bm25()
    _save_state()
    print(f"Built and saved index with {len(documents)} chunks.")


def add_to_index(new_docs: list[dict]):
    """
    Incrementally append new_docs to the existing index with deduplication.

    Pipeline:
      1. MD5 exact-duplicate filter   (O(n), no encoding needed)
      2. Encode survivors
      3. Cosine near-duplicate filter (FAISS search on existing index)
      4. Add survivors to FAISS, update global + per-doc state
    """
    global documents, texts, index, bm25

    if not new_docs:
        return

    # -- Step 1: Exact dedup ----------------------------------------------
    before_exact = len(new_docs)
    new_docs = _filter_exact_duplicates(new_docs)
    after_exact = len(new_docs)
    if before_exact != after_exact:
        print(f"  Exact dedup: {before_exact - after_exact} chunks removed.")

    if not new_docs:
        print("  All new chunks were exact duplicates - skipping.")
        return

    new_doc_id = new_docs[0].get("metadata", {}).get("doc_id", "unknown")
    new_texts = [doc["text"] for doc in new_docs]

    # -- Step 2: Encode ---------------------------------------------------
    print(f"Encoding {len(new_docs)} new chunks...")
    new_embeddings = embed_model.encode(new_texts, show_progress_bar=True, batch_size=16)
    new_embeddings = np.array(new_embeddings, dtype=np.float32)

    # -- Step 3: Near-duplicate dedup -------------------------------------
    before_near = len(new_docs)
    new_docs, new_embeddings = _filter_near_duplicates(new_docs, new_embeddings)
    after_near = len(new_docs)
    if before_near != after_near:
        print(f"  Near-dedup: {before_near - after_near} chunks removed.")

    if new_docs is None or len(new_docs) == 0:
        print("  All new chunks were near-duplicates - skipping.")
        return

    # -- Step 4: Add to FAISS ---------------------------------------------
    if index is None:
        index = _build_faiss_from_embeddings(new_embeddings)
    else:
        index.add(new_embeddings)

    documents.extend(new_docs)
    texts.extend([doc["text"] for doc in new_docs])

    _rebuild_bm25()
    _add_to_per_doc_bm25(new_doc_id, new_docs)
    _save_state()
    print(f"Index now has {len(documents)} chunks total ({len(per_doc_bm25)} PDFs). "
          f"Added {len(new_docs)} new chunks.")


def remove_from_index(doc_id: str):
    global documents, texts, index, bm25, per_doc_bm25, chunk_hashes

    survivors = [doc for doc in documents if doc.get("metadata", {}).get("doc_id") != doc_id]

    if len(survivors) == len(documents):
        print(f"Warning: no chunks found for doc_id={doc_id}")
        return

    removed = len(documents) - len(survivors)
    print(f"Removing {removed} chunks for doc_id={doc_id}, rebuilding index...")

    documents = survivors
    texts = [doc["text"] for doc in documents]
    # Rebuild hash cache from remaining texts
    chunk_hashes = {_md5(t) for t in texts}
    per_doc_bm25.pop(doc_id, None)

    if documents:
        embeddings = embed_model.encode(texts, show_progress_bar=False, batch_size=16)
        embeddings = np.array(embeddings, dtype=np.float32)
        index = _build_faiss_from_embeddings(embeddings)
        _rebuild_bm25()
    else:
        index = None
        bm25 = None

    _save_state()
    print(f"Index rebuilt with {len(documents)} chunks ({len(per_doc_bm25)} PDFs).")


def get_index():        return index
def get_documents():    return documents
def get_bm25():         return bm25
def get_per_doc_bm25(): return per_doc_bm25
def get_embed_model():  return embed_model