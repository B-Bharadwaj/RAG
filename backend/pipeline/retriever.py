"""
pipeline/retriever.py

Hybrid retrieval: FAISS dense + BM25 sparse, with proper per-doc scoping.

Search logic. hybrid_search() runs FAISS + BM25 in parallel and merges results. 
In scoped mode it uses the per-doc BM25 so IDF weights are computed on that PDF's own vocabulary.
per_pdf_search() guarantees representation from every indexed PDF 
by running a scoped search per doc_id before pooling. 
rerank() scores all candidates with a CrossEncoder. 
expand_query() generates query variations via Groq.
"""

import numpy as np
from sentence_transformers import CrossEncoder
from groq import Groq
from pipeline.indexer import (
    get_index, get_documents, get_bm25, get_per_doc_bm25, get_embed_model
)
from config import RERANKER_MODEL_NAME, GROQ_MODEL_NAME, TOP_K, GROQ_API_KEY
import os

os.environ["GROQ_API_KEY"] = GROQ_API_KEY
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("Loading reranker model...")
reranker = CrossEncoder(RERANKER_MODEL_NAME)
print("Reranker loaded!")


# ---------------------------------------------------------------------------
# Core retrieval
# ---------------------------------------------------------------------------

def hybrid_search(query: str, top_k: int = TOP_K, doc_id: str | None = None) -> list[dict]:
    """
    Hybrid FAISS + BM25 search with proper per-doc scoping.

    Global mode  (doc_id=None):
        FAISS searches all vectors; global BM25 scores all docs.

    Scoped mode  (doc_id set):
        FAISS searches all vectors then filters to doc_id chunks.
        BM25 uses the per-doc index built only from that PDF's corpus,
        so IDF weights reflect the document's own vocabulary.

    Parameters
    ----------
    query  : user query string
    top_k  : candidates to return per retriever before merging
    doc_id : restrict to this PDF only; None = all PDFs

    Returns
    -------
    Deduplicated list of document dicts (up to top_k * 2).
    """
    embed_model = get_embed_model()
    index = get_index()
    documents = get_documents()

    if index is None or not documents:
        return []

    fetch_k = top_k * 5 if doc_id else top_k

    # ── Dense (FAISS) ────────────────────────────────────────────────────
    query_embedding = np.array(embed_model.encode([query]), dtype=np.float32)
    D, I = index.search(query_embedding, min(fetch_k, len(documents)))
    vector_results = [documents[i] for i in I[0] if i < len(documents)]

    if doc_id:
        vector_results = [
            d for d in vector_results
            if d.get("metadata", {}).get("doc_id") == doc_id
        ]

    # ── Sparse (BM25) ────────────────────────────────────────────────────
    if doc_id:
        per_doc = get_per_doc_bm25()
        doc_bm25 = per_doc.get(doc_id)

        if doc_bm25 is not None:
            # Retrieve only this PDF's chunks in order
            doc_chunks = [
                d for d in documents
                if d.get("metadata", {}).get("doc_id") == doc_id
            ]
            scores = doc_bm25.get_scores(query.split())
            bm25_indices = np.argsort(scores)[::-1][:fetch_k]
            keyword_results = [
                doc_chunks[i] for i in bm25_indices if i < len(doc_chunks)
            ]
        else:
            # Fallback: global BM25 + post-filter (no per-doc index yet)
            global_bm25 = get_bm25()
            if global_bm25 is None:
                keyword_results = []
            else:
                scores = global_bm25.get_scores(query.split())
                bm25_indices = np.argsort(scores)[::-1][:fetch_k]
                keyword_results = [
                    documents[i] for i in bm25_indices if i < len(documents)
                ]
                keyword_results = [
                    d for d in keyword_results
                    if d.get("metadata", {}).get("doc_id") == doc_id
                ]
    else:
        global_bm25 = get_bm25()
        if global_bm25 is None:
            keyword_results = []
        else:
            scores = global_bm25.get_scores(query.split())
            bm25_indices = np.argsort(scores)[::-1][:fetch_k]
            keyword_results = [
                documents[i] for i in bm25_indices if i < len(documents)
            ]

    # ── Merge & deduplicate ──────────────────────────────────────────────
    combined = vector_results + keyword_results
    unique = {doc["text"]: doc for doc in combined}
    return list(unique.values())[: top_k * 2]


def per_pdf_search(query: str, top_k_per_pdf: int = 2) -> list[dict]:
    """
    Guarantee at least top_k_per_pdf chunks from EVERY indexed PDF.

    Used in All PDFs mode to prevent one strongly-matching paper from
    crowding out all others in the reranker input pool.

    Strategy
    --------
    For each registered doc_id, run a scoped hybrid_search() that uses
    that PDF's own per-doc BM25 + FAISS filter.  Collect top_k_per_pdf
    results per PDF, then return the full pool for the caller to rerank.

    Parameters
    ----------
    query          : user query string
    top_k_per_pdf  : minimum chunks to pull from each PDF

    Returns
    -------
    Flat deduplicated list of docs covering all indexed PDFs.
    """
    from pipeline.indexer import get_per_doc_bm25

    per_doc = get_per_doc_bm25()
    if not per_doc:
        return []

    all_results: list[dict] = []
    for did in per_doc:
        results = hybrid_search(query, top_k=top_k_per_pdf, doc_id=did)
        all_results.extend(results[:top_k_per_pdf])

    # Deduplicate while preserving order
    unique = {doc["text"]: doc for doc in all_results}
    return list(unique.values())


def rerank(query: str, docs: list[dict]) -> list[tuple[dict, float]]:
    """Score each doc against the query with a CrossEncoder and sort descending."""
    if not docs:
        return []
    pairs = [(query, doc["text"]) for doc in docs]
    scores = reranker.predict(pairs)
    return sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)


def expand_query(query: str) -> list[str]:
    """Generate 3 query variations via Groq LLaMA to improve recall."""
    response = client.chat.completions.create(
        model=GROQ_MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": (
                    "Generate 3 different versions of this question to improve search coverage. "
                    "Return only the questions, one per line, no numbering.\n"
                    f"Original question: {query}"
                ),
            }
        ],
    )
    variations = response.choices[0].message.content.strip().split("\n")
    variations = [v.strip() for v in variations if len(v.strip()) > 10]
    return [query] + variations[:3]