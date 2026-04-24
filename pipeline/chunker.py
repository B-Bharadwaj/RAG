"""
pipeline/chunker.py

Sentence-aware text chunking with doc_id tagging for multi-PDF support.

Changes from single-PDF version
---------------------------------
- create_documents() now accepts a mandatory  doc_id  argument.
- Every document dict carries  metadata["doc_id"]  so retrieval and
  deletion can be scoped to a specific PDF.
"""

import re
from config import CHUNK_SIZE, CHUNK_OVERLAP


def chunk_text_with_pages(pages_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    all_chunks = []
    for page_num, text in pages_text:
        sentences = re.split(r'(?<=[.!?]) +', text)
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
                    all_chunks.append((page_num, current_chunk.strip()))
                current_chunk = current_chunk[-overlap:] + sentence + " "
        if current_chunk.strip():
            all_chunks.append((page_num, current_chunk.strip()))
    return all_chunks


def create_documents(chunks_with_pages, pdf_name: str, doc_id: str) -> list[dict]:
    return [
        {
            "text": chunk,
            "type": "text",
            "metadata": {
                "source": "text",
                "page": page_num,
                "pdf": pdf_name,
                "doc_id": doc_id,
            },
        }
        for page_num, chunk in chunks_with_pages
    ]


# ---------------------------------------------------------------------------
# Reference section detection (mirrors generator.py logic)
# ---------------------------------------------------------------------------

_REFERENCE_SIGNALS = [
    "arXiv preprint arXiv:",
    "arXiv:",
    "Transactions of the Association",
    "IEEE Transactions on",
    "Proceedings of the",
    "Conference on Neural Information",
    "International Conference on",
    "Journal of Machine Learning",
    "et al.,",
    "et al. (",
    "pp. ",
    "vol. ",
]


def _is_reference_chunk(text: str) -> bool:
    """Return True if this chunk looks like a bibliography/reference page."""
    # Dense numbered citations like [127], [153]
    citation_count = len(re.findall(r'\[\d{2,3}\]', text))
    if citation_count >= 3:
        return True
    # arXiv IDs — very specific to reference sections
    arxiv_count = len(re.findall(r'arXiv[:\s]\d{4}\.\d{4,5}', text))
    if arxiv_count >= 3:
        return True
    # Multiple reference signals
    hits = sum(1 for sig in _REFERENCE_SIGNALS if sig in text)
    if hits >= 3:
        return True
    return False


def clean_documents(docs: list[dict]) -> list[dict]:
    """
    Filter out garbage chunks:
    - Too short or low word count
    - Low lexical diversity (repeated words)
    - Known bad phrases
    - Reference/bibliography sections (NEW)

    Image docs are exempt from word-ratio and reference checks.
    """
    cleaned = []
    garbage_phrases = [
        "text book", "upper right corner",
        "black and white image", "flow of water",
    ]

    for doc in docs:
        text     = doc["text"]
        doc_type = doc.get("type", "text")

        if len(text) < 30:
            continue
        if text.count(" ") < 5:
            continue

        if doc_type == "text":
            words = text.lower().split()
            if len(words) > 4:
                unique_ratio = len(set(words)) / len(words)
                if unique_ratio < 0.6:
                    continue
            if words.count("publication") > 1:
                continue
            if any(phrase in text.lower() for phrase in garbage_phrases):
                continue
            # Filter reference/bibliography chunks at index time
            if _is_reference_chunk(text):
                continue

        cleaned.append(doc)
    return cleaned
