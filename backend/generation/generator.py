"""
generation/generator.py

New features
------------
- Answer cache: exact-match query cache keyed by (query_lower, scope_key).
  Cache is in-memory, resets on server restart. Saves Groq API calls for
  repeated questions.
- generate_paper_summary(): generates a 3-paragraph summary of a full paper
  from its chunks. Called once at upload time from ui.py.
- generate_followup_suggestions(): after every answer, generates 3 follow-up
  questions shown as clickable buttons in the UI.
- Image chunk boosting: when the query mentions figures/diagrams, image chunks
  are force-included in the retrieval pool so the image panel fires.
"""

import os
import json
from groq import Groq
from pipeline.retriever import hybrid_search, per_pdf_search, rerank
from pipeline.indexer import get_per_doc_bm25, get_documents
from config import GROQ_API_KEY, GROQ_MODEL_NAME, GROQ_MODEL_LARGE, GROQ_MODEL_SMALL
from config import MAX_HISTORY_TURNS

os.environ["GROQ_API_KEY"] = GROQ_API_KEY
client = Groq(api_key=os.getenv("GROQ_API_KEY"))


class _Log:
    def info(self, msg, *a):    print(f"[INFO]  {msg % a if a else msg}")
    def debug(self, msg, *a):   pass
    def warning(self, msg, *a): print(f"[WARN]  {msg % a if a else msg}")
    def error(self, msg, *a):   print(f"[ERROR] {msg % a if a else msg}")

log = _Log()

_scoped_history: dict[str, list[dict]] = {}

_OVERVIEW_KEYWORDS = {
    "about", "topic", "summary", "summarise", "summarize", "overview",
    "contribution", "contribute", "propose", "proposed", "introduction",
    "abstract", "main idea", "what does", "what is the paper",
    "what are the papers", "focus", "purpose", "goal", "objective",
    "main contribution", "key contribution", "novel", "novelty",
    "method", "approach", "technique", "architecture", "model used",
}

# ── Image query detection ─────────────────────────────────────────────────────
# When the query mentions any of these, image chunks are force-included
# in the retrieval pool so the figure panel fires in the UI.
_IMAGE_KEYWORDS = {
    "figure", "fig", "diagram", "chart", "plot", "graph",
    "image", "illustration", "architecture diagram", "visuali",
    "show me", "explain the diagram", "explain the figure",
    "what does fig", "what is fig", "describe the", "draw",
    "table", "flowchart", "schematic",
}


def _is_image_query(query: str) -> bool:
    """Return True if the query is likely asking about a figure or diagram."""
    q_lower = query.lower()
    return any(kw in q_lower for kw in _IMAGE_KEYWORDS)


def reset_memory():
    global _scoped_history
    _scoped_history = {}
    log.info("Memory cleared.")


def _get_history(scope_key: str) -> list[dict]:
    return _scoped_history.setdefault(scope_key, [])


def _append_history(scope_key: str, query: str, answer: str):
    history = _get_history(scope_key)
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": answer})
    _scoped_history[scope_key] = history[-6:]


# ---------------------------------------------------------------------------
# Metadata extraction
# ---------------------------------------------------------------------------

def extract_pdf_metadata(first_page_text: str, filename: str) -> dict:
    prompt = (
        f"Extract the following fields from this academic paper's first page text.\n"
        f"Return ONLY a JSON object with exactly these keys: \"title\", \"authors\", \"abstract\".\n"
        f"- title: full paper title (string). If not found, use \"{filename}\".\n"
        f"- authors: all author names as a single comma-separated string. If not found, use \"Unknown\".\n"
        f"- abstract: the full abstract text (string). If not found, use \"\".\n"
        f"Do NOT include any explanation, markdown, or extra keys.\n\n"
        f"FIRST PAGE TEXT:\n{first_page_text[:3000]}\n\nJSON:"
    )
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.0,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        meta = json.loads(raw.strip())
        return {
            "title":    str(meta.get("title",    filename)),
            "authors":  str(meta.get("authors",  "Unknown")),
            "abstract": str(meta.get("abstract", "")),
        }
    except Exception as e:
        log.warning("Metadata extraction failed for '%s': %s", filename, e)
        return {"title": filename, "authors": "Unknown", "abstract": ""}


def _scope_label(doc_id: str | None) -> str:
    if doc_id is None:
        return "All PDFs"
    try:
        from pipeline.db import get_document
        doc = get_document(doc_id)
        if doc:
            meta = doc.get("pdf_metadata") or {}
            if isinstance(meta, dict):
                title = meta.get("title", "").strip()
                if title and title != doc.get("filename", ""):
                    return title
            return doc.get("filename", doc_id[:8])
    except Exception:
        pass
    return doc_id[:8]


# ---------------------------------------------------------------------------
# Summary generation
# ---------------------------------------------------------------------------

def generate_paper_summary(doc_id: str, pdf_name: str) -> str:
    import time as _time

    all_docs = get_documents()
    paper_chunks = [
        d for d in all_docs
        if d.get("metadata", {}).get("doc_id") == doc_id
        and d.get("type") == "text"
    ]
    paper_chunks.sort(key=lambda d: d.get("metadata", {}).get("page", 99))
    selected = paper_chunks[:4]

    if not selected:
        return ""

    context = "\n\n".join(
        f"[Page {d['metadata'].get('page','?')}] {d['text'][:250]}"
        for d in selected
    )

    prompt = (
        f"Based on these excerpts from '{pdf_name}', write a brief 3-paragraph summary:\n"
        f"- Para 1: Problem and motivation\n"
        f"- Para 2: Methods used\n"
        f"- Para 3: Key results\n"
        f"Be concise. Use only what's in the excerpts.\n\n"
        f"EXCERPTS:\n{context}\n\nSUMMARY:"
    )

    _time.sleep(2)

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.3,
            )
            summary = response.choices[0].message.content.strip()
            log.info("Summary generated for '%s'", pdf_name)
            return summary
        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err or "413" in err:
                wait = 10 if attempt == 0 else 20
                log.warning("Summary rate-limited for '%s', waiting %ds...", pdf_name, wait)
                _time.sleep(wait)
            else:
                log.warning("Summary failed for '%s': %s", pdf_name, e)
                return ""

    log.warning("Summary gave up after retries for '%s'", pdf_name)
    return ""


# ---------------------------------------------------------------------------
# Follow-up suggestions
# ---------------------------------------------------------------------------

def generate_followup_suggestions(query: str, answer: str, pdf_names: list[str]) -> list[str]:
    import time as _time

    prompt = (
        f"The user just asked: \"{query[:200]}\"\n\n"
        f"Generate 3 short follow-up questions they might ask next. "
        f"Return ONLY the 3 questions, one per line, no numbering."
    )

    _time.sleep(1)

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.7,
            )
            lines = response.choices[0].message.content.strip().split("\n")
            suggestions = [l.strip().lstrip("•-123456789. ") for l in lines if len(l.strip()) > 10]
            return suggestions[:3]
        except Exception as e:
            err = str(e).lower()
            if ("rate limit" in err or "429" in err or "413" in err) and attempt == 0:
                log.warning("Suggestions rate-limited, retrying in 5s...")
                _time.sleep(5)
            else:
                log.warning("Follow-up suggestions failed: %s", e)
                return []
    return []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_unique_pdfs(docs: list[dict]) -> int:
    return len(_get_unique_pdfs_in_docs(docs))


def _get_unique_pdfs_in_docs(docs: list[dict]) -> set[str]:
    names = set()
    for doc in docs:
        pdf = doc.get("metadata", {}).get("pdf", "unknown")
        # Strip any path prefix — keep only filename
        pdf = pdf.split("/")[-1].split("\\")[-1]
        names.add(pdf)
    return names


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
    import re
    citation_count = len(re.findall(r'\[\d{2,3}\]', text))
    if citation_count >= 3:
        return True
    arxiv_count = len(re.findall(r'arXiv[:\s]\d{4}\.\d{4,5}', text))
    if arxiv_count >= 3:
        return True
    hits = sum(1 for sig in _REFERENCE_SIGNALS if sig in text)
    if hits >= 3:
        return True
    return False


def _filter_reference_chunks(docs: list[dict]) -> list[dict]:
    filtered = []
    removed = 0
    for doc in docs:
        if doc.get("type") == "text" and _is_reference_chunk(doc.get("text", "")):
            removed += 1
        else:
            filtered.append(doc)
    if removed:
        log.info("Filtered %d reference/bibliography chunks", removed)
    return filtered


def _build_context(docs: list[dict]) -> str:
    from collections import defaultdict
    by_pdf: dict[str, list[dict]] = defaultdict(list)
    for doc in docs:
        pdf = doc.get("metadata", {}).get("pdf", "unknown")
        by_pdf[pdf].append(doc)

    parts = []
    for pdf_name, pdf_docs in by_pdf.items():
        pdf_docs.sort(key=lambda d: d.get("metadata", {}).get("page", 0))
        for doc in pdf_docs:
            doc_type = doc.get("type", "text").upper()
            meta     = doc.get("metadata", {})
            page     = meta.get("page", "?")
            parts.append(f"[{doc_type} — {pdf_name} — Page {page}]\n{doc['text']}")

    return "\n\n---\n\n".join(parts)


def _get_pdf_names() -> list[str]:
    from pipeline.db import get_all_documents
    return [d["filename"] for d in get_all_documents()]


def _is_overview_query(query: str) -> bool:
    q_lower = query.lower()
    return any(kw in q_lower for kw in _OVERVIEW_KEYWORDS)


# ---------------------------------------------------------------------------
# Early-page boosting
# ---------------------------------------------------------------------------

def _fetch_early_page_chunks(doc_id: str | None, pdf_names: list[str]) -> list[dict]:
    all_docs = get_documents()
    early_chunks = []
    per_doc = get_per_doc_bm25()
    target_doc_ids = {doc_id} if doc_id else set(per_doc.keys())

    for doc in all_docs:
        meta   = doc.get("metadata", {})
        d_id   = meta.get("doc_id", "")
        page   = meta.get("page", 99)
        d_type = doc.get("type", "text")
        if d_id in target_doc_ids and d_type == "text" and page <= 2:
            early_chunks.append(doc)

    log.debug("Early-page boost: %d text chunks from pages 1-2", len(early_chunks))
    return early_chunks


# ---------------------------------------------------------------------------
# Image chunk boosting — NEW
# ---------------------------------------------------------------------------

def _fetch_image_chunks(doc_id: str | None) -> list[dict]:
    """
    Return all image-type chunks, optionally scoped to one document.
    Called when the query is detected as asking about a figure or diagram.
    These chunks carry metadata["image_path"] which the UI uses to render
    the actual figure PNG alongside the answer.
    """
    all_docs = get_documents()
    image_chunks = [
        d for d in all_docs
        if d.get("type") == "image"
        and (
            doc_id is None
            or d.get("metadata", {}).get("doc_id") == doc_id
        )
    ]
    log.info("Image boost: found %d image chunks (doc_id=%s)", len(image_chunks), doc_id)
    return image_chunks


# ---------------------------------------------------------------------------
# Force-include all PDFs
# ---------------------------------------------------------------------------

def _ensure_all_pdfs_represented(
    ranked: list[tuple[dict, float]],
    top_docs_budget: int,
    all_pdf_names: list[str],
) -> list[dict]:
    filtered = [doc for doc, score in ranked if score > 0.5]
    if not filtered:
        filtered = [doc for doc, _ in ranked[:top_docs_budget]]

    top_docs = list(filtered[:top_docs_budget])
    covered  = _get_unique_pdfs_in_docs(top_docs)
    missing  = set(all_pdf_names) - covered

    for pdf_name in missing:
        added = 0
        for doc, score in ranked:
            if doc.get("metadata", {}).get("pdf") == pdf_name and added < 2:
                log.debug("Force-including chunk from '%s' (score=%.3f)", pdf_name, score)
                top_docs.append(doc)
                added += 1

    return top_docs


# ---------------------------------------------------------------------------
# Query rewriting
# ---------------------------------------------------------------------------

def _rewrite_query_for_multi_pdf(query: str, pdf_names: list[str]) -> str:
    names_str = ", ".join(pdf_names)
    prompt = (
        f"The user asked: \"{query}\"\n\n"
        f"There are {len(pdf_names)} research papers: {names_str}.\n"
        f"Rewrite so it explicitly asks about ALL papers with a separate answer for each. "
        f"Return ONLY the rewritten question."
    )
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.0,
        )
        rewritten = response.choices[0].message.content.strip().strip('"')
        log.debug("Query rewritten for multi-PDF: %r", rewritten)
        return rewritten
    except Exception:
        return query


# ---------------------------------------------------------------------------
# Standalone query resolution
# ---------------------------------------------------------------------------

def _resolve_standalone_query(query: str, scope_key: str) -> str:
    history = _get_history(scope_key)
    if not history:
        return query

    recent = history[-4:]
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
    )
    prompt = (
        f"Given this conversation history:\n{history_text}\n\n"
        f"And this new user question: \"{query}\"\n\n"
        f"Rewrite the question as a fully self-contained search query that can be "
        f"understood without the conversation history. "
        f"If the question is already self-contained, return it unchanged. "
        f"Return ONLY the rewritten question, no explanation."
    )
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=80,
            temperature=0.0,
        )
        resolved = response.choices[0].message.content.strip().strip('"')
        if resolved and resolved != query:
            log.debug("Query resolved: %r -> %r", query, resolved)
        return resolved or query
    except Exception:
        return query


# ---------------------------------------------------------------------------
# Prompt rules
# ---------------------------------------------------------------------------

_BASE_RULES = """\
RULES:
1. Use TEXT, IMAGE, and TABLE context equally as valid sources.
2. If the answer is directly stated, answer confidently.
3. If you must infer, say "Based on the context, it appears that..."
4. If the context is partially relevant, answer what you can and note the gap.
5. If the context has no relevant info for a specific paper, say so briefly for that paper only.
6. NEVER fabricate facts not present in the context.
7. The context you are given is complete. Trust it.
8. Do not over-generalize from a single chunk — synthesize across ALL context sections.
9. Answer ONLY about what the retrieved context says. Do NOT mix information from different
   papers unless the context explicitly contains both.
10. For single-paper answers: end with CONFIDENCE: High / Medium / Low"""

_MULTI_PDF_RULES = """\
11. Context comes from MULTIPLE papers. You MUST cover EVERY paper listed above.
    Use EXACTLY the filename as given in the papers list above — do not modify, shorten,
    or rename any filename under any circumstances.
    Structure your answer with EXACTLY this format — one block per paper, no exceptions:

    **[exact filename here]**
    [your answer for this paper in 2-3 sentences]
    CONFIDENCE: High / Medium / Low

    Rules:
    - Each paper gets exactly ONE block — never split a paper across multiple blocks
    - Never repeat the same filename twice
    - Never modify a filename — copy it exactly as shown in the papers list
    - Always end each block with CONFIDENCE on its own line
    - Leave one blank line between each paper block
    - After all paper blocks add a brief Overall Comparison if relevant

12. If a paper has no relevant context write exactly:
    **[exact filename here]**
    The retrieved context does not contain enough information.
    CONFIDENCE: Low

13. Only flag a conflict if two papers make DIRECTLY OPPOSING factual claims.
    Format: Conflict: [paperA.pdf] states X while [paperB.pdf] states Y."""


# ---------------------------------------------------------------------------
# Token budget controls
# ---------------------------------------------------------------------------

def _approx_tokens(text: str) -> int:
    return len(text) // 4


_MAX_CONTEXT_TOKENS = 3500
_MAX_CHUNK_CHARS    = 600
_MAX_HISTORY_TURNS  = 2


def _trim_context_to_budget(docs: list[dict]) -> list[dict]:
    trimmed = []
    for doc in docs:
        d = dict(doc)
        text = d.get("text", "")
        if len(text) > _MAX_CHUNK_CHARS:
            d["text"] = text[:_MAX_CHUNK_CHARS] + "..."
        trimmed.append(d)

    while trimmed and _approx_tokens(
        "\n".join(d["text"] for d in trimmed)
    ) > _MAX_CONTEXT_TOKENS:
        trimmed.pop()

    return trimmed


# ---------------------------------------------------------------------------
# Core generation
# ---------------------------------------------------------------------------

def generate_answer(
    query: str,
    context: str,
    scope_key: str,
    is_multi_pdf: bool = False,
    pdf_names: list[str] | None = None,
) -> str:
    rules = _BASE_RULES
    if is_multi_pdf:
        rules = rules + "\n" + _MULTI_PDF_RULES

    if is_multi_pdf and pdf_names:
        papers_line = (
            f"PAPERS — use EXACTLY these filenames, copy them character by character:\n"
            + "\n".join(f"  - {name}" for name in pdf_names)
            + "\n\n"
        )
    else:
        papers_line = ""

    system_content = (
        "You are a precise document analysis assistant. "
        "Answer questions using ONLY the provided context from research documents. "
        "Context may include TEXT, IMAGE descriptions, and TABLE data.\n\n"
        f"{papers_line}"
        f"{rules}\n\n"
        f"CONTEXT FOR THIS QUERY:\n{context}"
    )

    history = _get_history(scope_key)
    recent_history = history[-(_MAX_HISTORY_TURNS * 2):]

    messages = [{"role": "system", "content": system_content}]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": query})

    response = client.chat.completions.create(
        model=GROQ_MODEL_NAME,
        messages=messages,
        max_tokens=1024,
    )
    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Grounded query expansion
# ---------------------------------------------------------------------------

def expand_query_grounded(query: str, pdf_names: list[str], doc_id: str | None) -> list[str]:
    if doc_id is not None:
        from pipeline.db import get_document
        doc = get_document(doc_id)
        scope_hint = (
            f"These questions are about the paper: {doc['filename']}" if doc else ""
        )
    else:
        scope_hint = (
            f"These questions are about: {', '.join(pdf_names)}. "
            "Generate variations that retrieve content from ALL of them."
        ) if pdf_names else ""

    content = (
        f"{scope_hint}\n\n"
        "Generate 3 different search query variations to improve retrieval coverage. "
        "Return ONLY the questions, one per line, no numbering.\n\n"
        f"Original question: {query}"
    )
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": content}],
        )
        variations = response.choices[0].message.content.strip().split("\n")
        variations = [v.strip() for v in variations if len(v.strip()) > 10]
        return [query] + variations[:3]
    except Exception:
        return [query]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def ask_question(query: str, doc_id: str | None = None) -> tuple[str, list[dict], list[str], int]:
    """Returns (answer, sources, follow_up_suggestions, token_estimate)."""
    scope_key = doc_id if doc_id is not None else "global"
    pdf_names = _get_pdf_names()

    is_overview    = _is_overview_query(query)
    is_image_query = _is_image_query(query)   # NEW

    resolved_query = _resolve_standalone_query(query, scope_key)

    if doc_id is None:
        n_pdfs = max(len(get_per_doc_bm25()), 1)

        retrieval_query = (
            _rewrite_query_for_multi_pdf(resolved_query, pdf_names)
            if len(pdf_names) > 1 else resolved_query
        )

        queries = expand_query_grounded(retrieval_query, pdf_names, doc_id=None)
        pool: list[dict] = per_pdf_search(retrieval_query, top_k_per_pdf=5)
        for q in queries:
            pool.extend(hybrid_search(q, doc_id=None))

        if is_overview:
            pool.extend(_fetch_early_page_chunks(doc_id=None, pdf_names=pdf_names))

        # Force-include all image chunks so figure queries always find them
        if is_image_query:
            pool.extend(_fetch_image_chunks(doc_id=None))

        unique = {doc["text"]: doc for doc in pool}
        results = _filter_reference_chunks(list(unique.values()))
        top_docs_budget = min(max(n_pdfs * 2, 3), 8)

        ranked   = rerank(resolved_query, results)
        top_docs = _ensure_all_pdfs_represented(ranked, top_docs_budget, pdf_names)
        top_docs = _trim_context_to_budget(top_docs)
        top_docs.sort(key=lambda d: d.get("metadata", {}).get("pdf", ""))

    else:
        queries = expand_query_grounded(resolved_query, pdf_names, doc_id)
        pool = []
        for q in queries:
            pool.extend(hybrid_search(q, doc_id=doc_id))

        if is_overview:
            pool.extend(_fetch_early_page_chunks(doc_id=doc_id, pdf_names=pdf_names))

        # Force-include all image chunks for this doc so figure queries find them
        if is_image_query:
            pool.extend(_fetch_image_chunks(doc_id=doc_id))

        unique  = {doc["text"]: doc for doc in pool}
        results = _filter_reference_chunks(list(unique.values()))
        ranked  = rerank(resolved_query, results)

        filtered = [doc for doc, score in ranked if score > 0.5]
        if not filtered:
            filtered = [doc for doc, _ in ranked[:5]]

        # Give image queries a larger top-k so image chunks survive the cut
        top_k    = 5 if is_image_query else 3
        top_docs = _trim_context_to_budget(filtered[:top_k])

    is_multi_pdf = (doc_id is None) and (_count_unique_pdfs(top_docs) > 1)

    if is_multi_pdf:
        chunk_pdfs = sorted(_get_unique_pdfs_in_docs(top_docs))
        db_pdfs    = _get_pdf_names()
        present_pdf_names = []
        for chunk_name in chunk_pdfs:
            matched = next(
                (db for db in db_pdfs
                if db in chunk_name or chunk_name in db),
                chunk_name
            )
            if matched not in present_pdf_names:
                present_pdf_names.append(matched)
    else:
        present_pdf_names = None

    context = _build_context(top_docs)
    answer  = generate_answer(
        query, context, scope_key,
        is_multi_pdf=is_multi_pdf,
        pdf_names=present_pdf_names,
    )

    _append_history(scope_key, query, answer)

    token_estimate = _approx_tokens(context) + _approx_tokens(answer) + _approx_tokens(query)
    suggestions    = generate_followup_suggestions(query, answer, pdf_names)

    return answer, top_docs, suggestions, token_estimate


# ---------------------------------------------------------------------------
# Comparison mode
# ---------------------------------------------------------------------------

def ask_comparison(query: str, doc_ids: list[str]) -> tuple[str, list[dict]]:
    if not doc_ids:
        return "Please select at least 2 papers to compare.", []

    pdf_names = []
    for did in doc_ids:
        from pipeline.db import get_document
        doc = get_document(did)
        if doc:
            pdf_names.append(doc["filename"])

    pool: list[dict] = []
    for did in doc_ids:
        results = hybrid_search(query, top_k=4, doc_id=did)
        pool.extend(results)

    if not pool:
        return "No content retrieved for the selected papers.", []

    unique   = {doc["text"]: doc for doc in pool}
    results  = _filter_reference_chunks(list(unique.values()))
    ranked   = rerank(query, results)
    top_docs = _trim_context_to_budget([doc for doc, _ in ranked[:8]])

    context = _build_context(top_docs)

    papers_line = f"Papers being compared: {', '.join(pdf_names)}"

    comparison_prompt = (
        "You are a precise research comparison assistant.\n\n"
        f"{papers_line}\n\n"
        "RULES:\n"
        "1. Answer using ONLY the provided context.\n"
        "2. Structure your answer STRICTLY as:\n"
        "   - One block per paper: '**filename.pdf**: [findings]'\n"
        "   - A final '**Comparison**: [key similarities and differences]' block\n"
        "3. Be specific — cite actual numbers, methods, and results where available.\n"
        "4. If a paper has no relevant context for this question, say so in its block.\n"
        "5. NEVER fabricate information not in the context.\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"COMPARISON QUESTION:\n{query}\n\nANSWER:"
    )

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL_NAME,
            messages=[{"role": "user", "content": comparison_prompt}],
            max_tokens=1024,
        )
        answer = response.choices[0].message.content.strip()
        return answer, top_docs
    except Exception as e:
        log.error("Comparison failed: %s", e)
        return f"Comparison failed: {e}", []
    
# ===========================================================================
# v2 ADDITIONS — Business Intelligence generation functions
# ===========================================================================

from prompts import (
    SYSTEM_ANALYST,
    QA_PROMPT,
    INSIGHT_PROMPT,
    SUMMARY_PROMPT,
    ANOMALY_PROMPT,
    FOLLOWUP_PROMPT,
)

# In-memory chat history for business Q&A
# key = file_id, value = list of {role, content} dicts
_business_history: dict[str, list[dict]] = {}


def _get_business_history(file_id: str) -> list[dict]:
    return _business_history.setdefault(file_id, [])


def _append_business_history(file_id: str, query: str, answer: str):
    history = _get_business_history(file_id)
    history.append({"role": "user",      "content": query})
    history.append({"role": "assistant", "content": answer})
    # Keep only last 4 turns to save tokens
    _business_history[file_id] = history[-8:]


def reset_business_memory(file_id: str = None):
    """Clear business chat history for a file or all files."""
    global _business_history
    if file_id:
        _business_history.pop(file_id, None)
    else:
        _business_history = {}
    log.info("Business memory cleared.")


# ── Model Router ───────────────────────────────────────────────────────────

def _choose_model(task: str) -> str:
    """
    Route to the right model based on task complexity.
    Saves tokens on the free tier by using 8B for simple tasks.
    """
    from config import GROQ_MODEL_LARGE, GROQ_MODEL_SMALL
    complex_tasks = {"qa", "insights", "anomaly"}
    return GROQ_MODEL_LARGE if task in complex_tasks else GROQ_MODEL_SMALL


# ── Business Q&A ───────────────────────────────────────────────────────────

def ask_business_question(
    query: str,
    context: str,
    file_id: str,
    file_name: str,
) -> tuple[str, list[str]]:
    """
    Answer a business question about an Excel/CSV dataset.

    Parameters
    ----------
    query     : user's question
    context   : compressed data context from processor.py
    file_id   : used to scope chat history
    file_name : shown in prompts for context

    Returns
    -------
    (answer, follow_up_suggestions)
    """
    import time as _time

    model    = _choose_model("qa")
    history  = _get_business_history(file_id)
    recent   = history[-(MAX_HISTORY_TURNS * 2):]

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_ANALYST}]
    messages.extend(recent)
    messages.append({
        "role": "user",
        "content": QA_PROMPT.format(context=context, question=query)
    })

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model      = model,
                messages   = messages,
                max_tokens = 1000,
            )
            answer = response.choices[0].message.content.strip()
            _append_business_history(file_id, query, answer)

            # Generate follow up suggestions
            suggestions = _business_followup_suggestions(query, answer)
            return answer, suggestions

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                log.warning("Rate limited, waiting %ds...", wait)
                _time.sleep(wait)
            else:
                log.error("Business Q&A failed: %s", e)
                return f"Error generating answer: {e}", []

    return "Failed after retries — please try again.", []


# ── Auto Insights ──────────────────────────────────────────────────────────

def generate_business_insights(context: str, file_name: str) -> str:
    """
    Auto generate 5 business insights from the dataset summary.
    Called once when a file is uploaded.
    """
    import time as _time

    model = _choose_model("insights")

    for attempt in range(3):
        try:
            _time.sleep(2)  # polite delay for free tier
            response = client.chat.completions.create(
                model      = model,
                messages   = [
                    {"role": "system", "content": SYSTEM_ANALYST},
                    {"role": "user",   "content": INSIGHT_PROMPT.format(context=context)},
                ],
                max_tokens = 1000,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 15 * (attempt + 1)
                log.warning("Insights rate limited, waiting %ds...", wait)
                _time.sleep(wait)
            else:
                log.error("Insights generation failed: %s", e)
                return ""

    return ""


# ── Executive Summary ──────────────────────────────────────────────────────

def generate_executive_summary(context: str, file_name: str) -> str:
    """
    Generate a professional executive summary for a business file.
    Called from the UI when user clicks Generate Summary.
    """
    import time as _time

    model = _choose_model("summary")

    for attempt in range(3):
        try:
            _time.sleep(2)
            response = client.chat.completions.create(
                model      = model,
                messages   = [
                    {"role": "system", "content": SYSTEM_ANALYST},
                    {
                        "role": "user",
                        "content": SUMMARY_PROMPT.format(
                            context   = context,
                            file_name = file_name,
                        )
                    },
                ],
                max_tokens = 1000,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 15 * (attempt + 1)
                log.warning("Summary rate limited, waiting %ds...", wait)
                _time.sleep(wait)
            else:
                log.error("Summary generation failed: %s", e)
                return ""

    return ""


# ── Anomaly Explanation ────────────────────────────────────────────────────

def explain_anomalies(context: str, anomalies: list[dict]) -> str:
    """
    Explain detected anomalies in plain business language.
    """
    import time as _time

    if not anomalies:
        return "No anomalies detected in this dataset."

    model = _choose_model("anomaly")

    anomaly_text = "\n".join(
        f"- [{a['severity'].upper()}] {a['detail']}"
        for a in anomalies
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model      = model,
                messages   = [
                    {"role": "system", "content": SYSTEM_ANALYST},
                    {
                        "role": "user",
                        "content": ANOMALY_PROMPT.format(
                            context   = context,
                            anomalies = anomaly_text,
                        )
                    },
                ],
                max_tokens = 800,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                _time.sleep(wait)
            else:
                log.error("Anomaly explanation failed: %s", e)
                return ""

    return ""


# ── Follow-up Suggestions ──────────────────────────────────────────────────

def _business_followup_suggestions(query: str, answer: str) -> list[str]:
    """Generate 3 follow-up questions after a business Q&A response."""
    import time as _time

    try:
        _time.sleep(1)
        response = client.chat.completions.create(
            model      = GROQ_MODEL_SMALL,
            messages   = [{
                "role": "user",
                "content": FOLLOWUP_PROMPT.format(
                    question = query[:200],
                    answer   = answer[:300],
                )
            }],
            max_tokens = 100,
        )
        lines = response.choices[0].message.content.strip().split("\n")
        return [l.strip() for l in lines if len(l.strip()) > 5][:3]

    except Exception as e:
        log.warning("Follow-up suggestions failed: %s", e)
        return []
    
    
def ask_business_question_with_chart(
    query: str,
    context: str,
    file_id: str,
    file_name: str,
    df,                    # pandas DataFrame — for chart generation
) -> tuple[str, list[str], dict | None]:
    """
    Extended version of ask_business_question that also
    auto generates a chart if the question is chart-worthy.

    Returns
    -------
    (answer, follow_up_suggestions, chart_result_or_None)
    """
    from services.chart_generator import needs_chart, generate_chat_chart

    # Step 1 — get text answer as normal
    answer, suggestions = ask_business_question(
        query     = query,
        context   = context,
        file_id   = file_id,
        file_name = file_name,
    )

    # Step 2 — check if chart is needed
    chart_result = None
    if needs_chart(query) and df is not None:
        try:
            chart_result = generate_chat_chart(
                query       = query,
                df          = df,
                file_id     = file_id,
                file_name   = file_name,
                groq_client = client,
                model       = GROQ_MODEL_SMALL,
            )
        except Exception as e:
            log.warning("Chat chart generation failed: %s", e)
            chart_result = None

    return answer, suggestions, chart_result

# =============================================================================
# v3 ADDITIONS — Text-to-SQL generation
# =============================================================================

from prompts import SQL_GENERATION_PROMPT, SQL_ANSWER_PROMPT


def generate_sql_query(
    question: str,
    schema:   str,
) -> str:
    """
    Ask the LLM to generate a PostgreSQL SQL query
    for the given question and database schema.

    Returns the raw SQL string or 'NOT_SQL' if the
    question cannot be answered with SQL.
    """
    import time as _time

    prompt = SQL_GENERATION_PROMPT.format(
        schema   = schema,
        question = question,
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model       = GROQ_MODEL_LARGE,
                messages    = [{"role": "user", "content": prompt}],
                max_tokens  = 500,
                temperature = 0.0,
            )
            sql = response.choices[0].message.content.strip()

            # Strip accidental markdown fences
            if sql.startswith("```"):
                parts = sql.split("```")
                sql   = parts[1] if len(parts) > 1 else sql
                if sql.lower().startswith("sql"):
                    sql = sql[4:]

            return sql.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                log.warning("SQL gen rate limited, waiting %ds...", wait)
                _time.sleep(wait)
            else:
                log.error("SQL generation failed: %s", e)
                return "NOT_SQL"

    return "NOT_SQL"


def sql_result_to_answer(
    question: str,
    columns:  list,
    rows:     list,
) -> str:
    """
    Convert SQL query results into a natural language answer.
    Takes the exact rows returned from PostgreSQL and asks
    the LLM to explain them in plain business English.
    """
    import time as _time

    prompt = SQL_ANSWER_PROMPT.format(
        question = question,
        columns  = columns,
        rows     = rows[:10],
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model      = GROQ_MODEL_SMALL,
                messages   = [{"role": "user", "content": prompt}],
                max_tokens = 300,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                log.warning("SQL answer rate limited, waiting %ds...", wait)
                _time.sleep(wait)
            else:
                log.error("SQL answer generation failed: %s", e)
                return f"Query returned {len(rows)} rows with columns: {columns}"

    return f"Query returned {len(rows)} rows with columns: {columns}"

# =============================================================================
# v3 ADDITIONS — SQL-driven summary and anomaly generation
# =============================================================================

from prompts import (
    SQL_SUMMARY_QUERIES_PROMPT,
    SQL_SUMMARY_GENERATION_PROMPT,
    SQL_ANOMALY_QUERIES_PROMPT,
    SQL_ANOMALY_EXPLANATION_PROMPT,
)


def generate_summary_queries(schema: str) -> list[str]:
    """
    Ask LLM to generate 5 SQL queries that give a business overview
    of the dataset. Returns a list of SQL strings.
    """
    import time as _time
    import json as _json

    prompt = SQL_SUMMARY_QUERIES_PROMPT.format(schema=schema)

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model       = GROQ_MODEL_LARGE,
                messages    = [{"role": "user", "content": prompt}],
                max_tokens  = 1000,
                temperature = 0.0,
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown fences if present
            if "```" in raw:
                parts = raw.split("```")
                raw   = parts[1] if len(parts) > 1 else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]

            queries = _json.loads(raw.strip())
            if isinstance(queries, list):
                return queries

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                log.warning("Summary query gen rate limited, waiting %ds", wait)
                _time.sleep(wait)
            else:
                log.error("Summary query generation failed: %s", e)
                return []

    return []


def generate_sql_summary(
    file_name: str,
    schema:    str,
    results:   str,
) -> str:
    """
    Generate a business summary from SQL query results.
    """
    import time as _time

    prompt = SQL_SUMMARY_GENERATION_PROMPT.format(
        file_name = file_name,
        results   = results,
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model      = GROQ_MODEL_LARGE,
                messages   = [{"role": "user", "content": prompt}],
                max_tokens = 500,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                _time.sleep(wait)
            else:
                log.error("SQL summary generation failed: %s", e)
                return "Summary generation failed."

    return "Summary generation failed."


def generate_anomaly_queries(schema: str) -> list[str]:
    """
    Ask LLM to generate 4 SQL queries for anomaly/data quality detection.
    Returns a list of SQL strings.
    """
    import time as _time
    import json as _json

    prompt = SQL_ANOMALY_QUERIES_PROMPT.format(schema=schema)

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model       = GROQ_MODEL_LARGE,
                messages    = [{"role": "user", "content": prompt}],
                max_tokens  = 1000,
                temperature = 0.0,
            )
            raw = response.choices[0].message.content.strip()

            if "```" in raw:
                parts = raw.split("```")
                raw   = parts[1] if len(parts) > 1 else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]

            queries = _json.loads(raw.strip())
            if isinstance(queries, list):
                return queries

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                _time.sleep(wait)
            else:
                log.error("Anomaly query generation failed: %s", e)
                return []

    return []


def generate_sql_anomaly_explanation(
    file_name: str,
    results:   str,
) -> str:
    """
    Explain anomaly detection results in plain business English.
    """
    import time as _time

    prompt = SQL_ANOMALY_EXPLANATION_PROMPT.format(
        file_name = file_name,
        results   = results,
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model      = GROQ_MODEL_LARGE,
                messages   = [{"role": "user", "content": prompt}],
                max_tokens = 400,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                _time.sleep(wait)
            else:
                log.error("Anomaly explanation failed: %s", e)
                return "Anomaly explanation failed."

    return "Anomaly explanation failed."

from prompts import SQL_CHART_PROMPT

def generate_sql_chart_query(
    question:        str,
    schema:          str,
    specific_values: dict = None,
) -> dict:
    """
    Ask LLM to generate a SQL query specifically for chart generation.
    Passes detected specific values so LLM can use WHERE IN filtering.

    Returns dict with:
        sql        → PostgreSQL query to run
        chart_type → bar, line, pie, scatter, hist
        x_col      → column for X axis
        y_col      → column for Y axis
        title      → chart title
    """
    import time as _time
    import json as _json

    # Format specific values for the prompt
    if specific_values:
        sv_text = "\n".join(
            f"  {col}: {vals}"
            for col, vals in specific_values.items()
        )
    else:
        sv_text = "  None detected — show top 10 by value"

    prompt = SQL_CHART_PROMPT.format(
        schema          = schema,
        specific_values = sv_text,
        question        = question,
    )

    for attempt in range(3):
        try:
            _time.sleep(1)
            response = client.chat.completions.create(
                model       = GROQ_MODEL_LARGE,
                messages    = [{"role": "user", "content": prompt}],
                max_tokens  = 500,
                temperature = 0.0,
            )
            raw = response.choices[0].message.content.strip()

            # Strip markdown fences
            if "```" in raw:
                parts = raw.split("```")
                raw   = parts[1] if len(parts) > 1 else raw
                if raw.lower().startswith("json"):
                    raw = raw[4:]

            result = _json.loads(raw.strip())

            # Validate required fields
            required = ["sql", "chart_type", "x_col", "y_col", "title"]
            if all(k in result for k in required):
                return result

        except Exception as e:
            err = str(e).lower()
            if "rate limit" in err or "429" in err:
                wait = 10 * (attempt + 1)
                log.warning("Chart query gen rate limited, waiting %ds", wait)
                _time.sleep(wait)
            else:
                log.error("Chart query generation failed: %s", e)
                return {"sql": "NOT_SQL"}

    return {"sql": "NOT_SQL"}
