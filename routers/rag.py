"""
routers/rag.py

FastAPI endpoints for the v1 PDF RAG pipeline.
All v1 pipeline functions are called directly — nothing modified.

Endpoints:
    POST   /upload              — upload + process a PDF
    POST   /chat                — ask a question
    POST   /compare             — compare 2-3 papers
    GET    /documents           — list all indexed documents
    GET    /documents/{doc_id}  — get document info + summary
    DELETE /documents/{doc_id}  — delete a document
    DELETE /memory              — clear conversation memory
    POST   /eval/score          — score recent queries
    GET    /eval/results        — get eval scores + summary
    DELETE /eval/results        — clear eval scores
    GET    /health              — health check
"""

import os
import tempfile
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel

from pipeline.loader  import load_pdf, extract_images
from pipeline.ocr     import caption_images
from pipeline.chunker import chunk_text_with_pages, create_documents, clean_documents
from pipeline.indexer import add_to_index, load_state, remove_from_index
from pipeline.db      import (
    generate_doc_id, register_document, get_all_documents,
    delete_document, update_document_metadata, update_document_summary,
    filename_exists, get_document,
    save_question, get_question_history,
    get_eval_scores, get_eval_summary, clear_eval_scores,
)
from generation.generator import (
    ask_question, reset_memory,
    extract_pdf_metadata, generate_paper_summary, ask_comparison,
)

router = APIRouter()

MAX_FILE_SIZE_MB = 50
MAX_PAGE_COUNT   = 100


# ── Pydantic schemas ───────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    query:  str
    doc_id: Optional[str] = None   # None = search all PDFs


class CompareRequest(BaseModel):
    query:   str
    doc_ids: list[str]             # 2 or 3 doc IDs to compare


class EvalRequest(BaseModel):
    n: int = 10                    # number of recent queries to score


# ── Helpers ────────────────────────────────────────────────────────────────

def _validate_pdf(path: str, name: str) -> int:
    """Validate PDF size and page count. Returns page count."""
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"'{name}' is {size_mb:.1f} MB — exceeds {MAX_FILE_SIZE_MB} MB.")
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
    try:
        n = len(PdfReader(path).pages)
    except PdfReadError as e:
        raise ValueError(f"Not a valid PDF: {e}")
    if n == 0:
        raise ValueError(f"'{name}' has no pages.")
    if n > MAX_PAGE_COUNT:
        raise ValueError(f"'{name}' has {n} pages — exceeds {MAX_PAGE_COUNT}.")
    return n


# ── Health ─────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check — confirms the RAG API is running."""
    docs = get_all_documents()
    return {
        "status":        "ok",
        "version":       "1.0",
        "pipeline":      "RAG",
        "docs_indexed":  len(docs),
    }


# ── Upload PDF ─────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload and process a PDF through the full v1 RAG pipeline:
    text extraction → chunking → OCR → FAISS + BM25 indexing
    → metadata extraction → summary generation
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    file_bytes = await file.read()

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        # Validate
        try:
            page_count = _validate_pdf(tmp_path, file.filename)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        # Check duplicate
        if filename_exists(file.filename):
            doc = next(
                (d for d in get_all_documents() if d["filename"] == file.filename),
                None
            )
            return {
                "status":     "already_exists",
                "doc_id":     doc["doc_id"] if doc else None,
                "filename":   file.filename,
                "page_count": page_count,
                "message":    "PDF already indexed. Use existing doc_id for queries.",
            }

        doc_id = generate_doc_id()

        # Text extraction
        pages_text = load_pdf(tmp_path)
        chunks     = chunk_text_with_pages(pages_text)
        text_docs  = create_documents(chunks, file.filename, doc_id)

        # OCR / figure extraction
        images     = extract_images(tmp_path)
        image_docs = caption_images(images, file.filename, doc_id, pdf_path=tmp_path)

        # Index
        all_docs = clean_documents(text_docs + image_docs)
        add_to_index(all_docs)
        register_document(doc_id, file.filename, page_count, len(all_docs))

        # Metadata
        first_page = pages_text[0][1] if pages_text else ""
        meta = extract_pdf_metadata(first_page, file.filename)
        update_document_metadata(doc_id, meta)

        # Summary
        summary = generate_paper_summary(doc_id, file.filename)
        if summary:
            update_document_summary(doc_id, summary)

        return {
            "status":      "success",
            "doc_id":      doc_id,
            "filename":    file.filename,
            "page_count":  page_count,
            "chunk_count": len(all_docs),
            "title":       meta.get("title", file.filename),
            "authors":     meta.get("authors", "Unknown"),
            "summary":     summary or "",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")
    finally:
        os.unlink(tmp_path)


# ── Chat ───────────────────────────────────────────────────────────────────

@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Ask a question about indexed PDFs.
    Set doc_id to scope to a specific PDF, or leave None for all PDFs.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        answer, sources, suggestions, token_estimate = ask_question(
            request.query,
            doc_id=request.doc_id,
        )

        save_question(request.query, answer, request.doc_id or "All PDFs")

        # Format sources for API response
        formatted_sources = []
        for s in sources:
            meta = s.get("metadata", {})
            formatted_sources.append({
                "type":      s.get("type", "text"),
                "pdf":       meta.get("pdf", "unknown"),
                "page":      meta.get("page", "?"),
                "preview":   s["text"][:200],
                "image_path":meta.get("image_path", None),
            })

        return {
            "query":          request.query,
            "answer":         answer,
            "sources":        formatted_sources,
            "follow_ups":     suggestions,
            "token_estimate": token_estimate,
            "scope":          request.doc_id or "All PDFs",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {e}")


# ── Compare ────────────────────────────────────────────────────────────────

@router.post("/compare")
async def compare(request: CompareRequest):
    """
    Compare 2-3 papers side by side on a specific question.
    Provide doc_ids of the papers to compare.
    """
    if len(request.doc_ids) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 doc_ids required for comparison."
        )
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    try:
        answer, sources = ask_comparison(request.query, request.doc_ids)

        formatted_sources = []
        for s in sources:
            meta = s.get("metadata", {})
            formatted_sources.append({
                "type":    s.get("type", "text"),
                "pdf":     meta.get("pdf", "unknown"),
                "page":    meta.get("page", "?"),
                "preview": s["text"][:200],
            })

        return {
            "query":    request.query,
            "answer":   answer,
            "sources":  formatted_sources,
            "doc_ids":  request.doc_ids,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


# ── Document Management ────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents():
    """List all indexed PDF documents with metadata."""
    docs = get_all_documents()
    result = []
    for d in docs:
        meta = d.get("pdf_metadata") or {}
        result.append({
            "doc_id":      d["doc_id"],
            "filename":    d["filename"],
            "page_count":  d["page_count"],
            "chunk_count": d["chunk_count"],
            "uploaded_at": d["uploaded_at"],
            "title":       meta.get("title", d["filename"]),
            "authors":     meta.get("authors", "Unknown"),
            "has_summary": bool(d.get("pdf_summary")),
        })
    return {"total": len(result), "documents": result}


@router.get("/documents/{doc_id}")
async def get_document_info(doc_id: str):
    """Get detailed info about a specific document including abstract and summary."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    meta = doc.get("pdf_metadata") or {}
    return {
        "doc_id":      doc["doc_id"],
        "filename":    doc["filename"],
        "page_count":  doc["page_count"],
        "chunk_count": doc["chunk_count"],
        "uploaded_at": doc["uploaded_at"],
        "title":       meta.get("title", doc["filename"]),
        "authors":     meta.get("authors", "Unknown"),
        "abstract":    meta.get("abstract", ""),
        "summary":     doc.get("pdf_summary", ""),
    }


@router.delete("/documents/{doc_id}")
async def delete_document_endpoint(doc_id: str):
    """
    Delete a document from the index and database.
    Also removes saved figure images for this document.
    """
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found.")

    try:
        remove_from_index(doc_id)
        delete_document(doc_id)
        reset_memory()

        # Clean up saved figure images
        images_dir = os.path.join("storage", "images")
        removed_images = 0
        if os.path.exists(images_dir):
            for fname in os.listdir(images_dir):
                if fname.startswith(doc_id):
                    try:
                        os.remove(os.path.join(images_dir, fname))
                        removed_images += 1
                    except Exception:
                        pass

        return {
            "status":         "deleted",
            "doc_id":         doc_id,
            "filename":       doc["filename"],
            "images_removed": removed_images,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")


# ── Memory ─────────────────────────────────────────────────────────────────

@router.delete("/memory")
async def clear_memory():
    """Clear all conversation memory."""
    reset_memory()
    return {"status": "cleared", "message": "Conversation memory has been reset."}


@router.get("/history")
async def get_history(limit: int = 20):
    """Get recent chat history."""
    history = get_question_history(limit=limit)
    return {"total": len(history), "history": history}


# ── Evaluation ─────────────────────────────────────────────────────────────

@router.post("/eval/score")
async def score_queries(request: EvalRequest):
    """
    Score the most recent N un-scored chat queries using the judge LLM.
    Uses llama-3.3-70b to score Faithfulness, Relevancy, and Context Recall.
    """
    try:
        from eval.run_eval import run_on_recent_queries
        results = run_on_recent_queries(n=request.n)

        if not results:
            return {
                "status":  "no_queries",
                "message": "No un-scored queries found. Chat with PDFs first.",
                "scored":  0,
            }

        scored = [r for r in results if r.get("faithfulness", -1) >= 0]
        failed = len(results) - len(scored)

        return {
            "status":  "success",
            "scored":  len(scored),
            "failed":  failed,
            "results": scored,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scoring failed: {e}")


@router.get("/eval/results")
async def get_eval_results(limit: int = 50):
    """Get evaluation scores and summary statistics."""
    summary = get_eval_summary()
    rows    = get_eval_scores(limit=limit)

    return {
        "summary": summary,
        "scores":  rows,
    }


@router.delete("/eval/results")
async def clear_eval():
    """Clear all evaluation scores."""
    clear_eval_scores()
    return {"status": "cleared", "message": "All eval scores have been deleted."}
