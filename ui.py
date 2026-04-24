"""
ui.py — Multi-PDF RAG Assistant

Compatible with Gradio 3.x and 4.x.
- No show_copy_button (added in newer Gradio)
- No type="messages" (added in newer Gradio)
- Chat history uses (user_msg, assistant_msg) tuples — works everywhere.

Changes from original
---------------------
- Chat tab switched from gr.ChatInterface to a manual chatbot layout so
  we can show a figure image panel alongside the answer when a source
  chunk has image_path in its metadata (saved by ocr.py).
- source_image panel appears automatically when retrieved chunks include
  a page with a saved figure. Hidden otherwise.
- All other tabs (Upload, Manage, Compare, Eval) are unchanged.
"""

import gradio as gr
import time
import os
import re
import pandas as pd
from collections import defaultdict
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pipeline.loader import load_pdf, extract_images
from pipeline.ocr import caption_images
from pipeline.indexer import add_to_index, get_index, load_state, remove_from_index
from pipeline.chunker import chunk_text_with_pages, create_documents, clean_documents
from pipeline.db import (
    generate_doc_id, register_document, get_all_documents, get_document,
    delete_document, update_document_metadata, update_document_summary,
    filename_exists, save_question,
)
from generation.generator import (
    ask_question, reset_memory, extract_pdf_metadata,
    generate_paper_summary, ask_comparison,
)
from config import MAX_REQUESTS_PER_MINUTE

try:
    from logger import get_logger
    log = get_logger(__name__)
except Exception:
    class _Log:
        def info(self, m, *a):    print(f"[INFO]  {m % a if a else m}")
        def warning(self, m, *a): print(f"[WARN]  {m % a if a else m}")
        def error(self, m, *a):   print(f"[ERROR] {m % a if a else m}")
        def debug(self, m, *a):   pass
    log = _Log()

load_state()

MAX_FILE_SIZE_MB = 50
MAX_PAGE_COUNT   = 100
MAX_SUGGESTIONS  = 3

_rate_limit_store: dict[str, tuple[int, float]] = defaultdict(lambda: (0, time.time()))

def dict_to_tuple(d: dict) -> tuple:
    return tuple(d.values())

def _check_rate_limit(session_id: str) -> bool:
    count, window_start = _rate_limit_store[session_id]
    now = time.time()
    if now - window_start > 60:
        _rate_limit_store[session_id] = (1, now)
        return True
    if count >= MAX_REQUESTS_PER_MINUTE:
        return False
    _rate_limit_store[session_id] = (count + 1, window_start)
    return True


# ---------------------------------------------------------------------------
# PDF validation
# ---------------------------------------------------------------------------

def _validate_pdf(pdf_path: str, pdf_name: str) -> int:
    size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"'{pdf_name}' is {size_mb:.1f} MB — exceeds {MAX_FILE_SIZE_MB} MB limit.")
    try:
        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
    except PdfReadError as e:
        raise ValueError(f"'{pdf_name}' is corrupted or not a valid PDF: {e}")
    if page_count == 0:
        raise ValueError(f"'{pdf_name}' has no pages.")
    if page_count > MAX_PAGE_COUNT:
        raise ValueError(f"'{pdf_name}' has {page_count} pages — exceeds {MAX_PAGE_COUNT} limit.")
    return page_count


# ---------------------------------------------------------------------------
# Single PDF processing
# ---------------------------------------------------------------------------

def _process_single_pdf(pdf_path, pdf_name, progress_fn=None):
    def _prog(frac, desc=""):
        if progress_fn:
            progress_fn(frac, desc)

    _prog(0.0, "Validating…")
    yield f"Validating '{pdf_name}'..."
    try:
        page_count = _validate_pdf(pdf_path, pdf_name)
    except ValueError as e:
        yield f"[WARN] {e}"; return

    if filename_exists(pdf_name):
        yield f"[WARN] '{pdf_name}' already indexed - skipping."; return

    doc_id = generate_doc_id()

    _prog(0.05, "Extracting text...")
    yield f"[{pdf_name}] Extracting text from {page_count} pages..."
    try:
        pages_text = load_pdf(pdf_path)
        chunks     = chunk_text_with_pages(pages_text)
        text_docs  = create_documents(chunks, pdf_name, doc_id)
    except Exception as e:
        yield f"[ERROR] [{pdf_name}] Text extraction failed: {e}"; return

    _prog(0.15, "Extracting images...")
    yield f"[{pdf_name}] Rendering page images..."
    try:
        images = extract_images(pdf_path)
    except Exception as e:
        yield f"[ERROR] [{pdf_name}] Image extraction failed: {e}"; return

    _prog(0.20, "Starting OCR...")
    yield f"[{pdf_name}] Captioning {page_count} pages..."

    def _ocr_cb(completed, total):
        _prog(0.20 + 0.50 * (completed / total), f"OCR {completed}/{total}...")

    try:
        image_docs = caption_images(images, pdf_name, doc_id, progress_callback=_ocr_cb)
    except Exception as e:
        yield f"[ERROR] [{pdf_name}] OCR failed: {e}"; return

    _prog(0.72, "Cleaning...")
    yield f"[{pdf_name}] Cleaning chunks..."
    all_docs = clean_documents(text_docs + image_docs)

    _prog(0.78, "Encoding...")
    yield f"[{pdf_name}] Encoding {len(all_docs)} chunks..."
    try:
        add_to_index(all_docs)
    except Exception as e:
        yield f"[ERROR] [{pdf_name}] Indexing failed: {e}"; return

    _prog(0.90, "Saving...")
    try:
        register_document(doc_id, pdf_name, page_count, len(all_docs))
    except Exception as e:
        yield f"[ERROR] [{pdf_name}] Registry write failed: {e}"; return

    _prog(0.93, "Extracting metadata...")
    yield f"[{pdf_name}] Extracting metadata..."
    try:
        first_page_text = pages_text[0][1] if pages_text else ""
        meta = extract_pdf_metadata(first_page_text, pdf_name)
        update_document_metadata(doc_id, meta)
    except Exception as e:
        log.warning("Metadata failed for %s: %s", pdf_name, e)
        meta = {"title": pdf_name, "authors": "Unknown", "abstract": ""}

    _prog(0.97, "Generating summary...")
    yield f"[{pdf_name}] Generating paper summary..."
    try:
        summary = generate_paper_summary(doc_id, pdf_name)
        if summary:
            update_document_summary(doc_id, summary)
    except Exception as e:
        log.warning("Summary failed for %s: %s", pdf_name, e)

    _prog(1.0, "Done!")
    yield f"[DONE] '{meta['title']}' - {len(all_docs)} chunks across {page_count} pages."


# ---------------------------------------------------------------------------
# Multi-file upload
# ---------------------------------------------------------------------------

def process_pdfs(pdf_files, progress=gr.Progress(track_tqdm=False)):
    if not pdf_files:
        yield "No files provided.", gr.update(); return
    if not isinstance(pdf_files, list):
        pdf_files = [pdf_files]

    total = len(pdf_files)
    all_status = []

    for i, f in enumerate(pdf_files):
        s, e = i / total, (i + 1) / total
        def _prog(frac, desc="", _s=s, _e=e, _i=i):
            progress(_s + frac * (_e - _s), desc=f"[{_i+1}/{total}] {desc}")
        for status in _process_single_pdf(f.name, os.path.basename(f.name), _prog):
            all_status.append(status)
            yield "\n".join(all_status[-8:]), gr.update()

    progress(1.0, desc="All done!")
    yield "\n".join(all_status), gr.update(choices=_scope_choices(), value="All PDFs")


# ---------------------------------------------------------------------------
# PDF deletion
# ---------------------------------------------------------------------------

def delete_pdf(doc_id: str):
    if not doc_id or not doc_id.strip():
        return "Enter a Doc ID.", _render_doc_table(), gr.update()
    doc_id = doc_id.strip()
    try:
        remove_from_index(doc_id)
        delete_document(doc_id)
        reset_memory()
        return f"Deleted {doc_id[:8]}...", _render_doc_table(), gr.update(choices=_scope_choices(), value="All PDFs")
    except Exception:
        try:
            delete_document(doc_id)
            reset_memory()
            return f"Deleted {doc_id[:8]}... (registry cleaned up).", _render_doc_table(), gr.update(choices=_scope_choices(), value="All PDFs")
        except Exception as e2:
            return f"Delete failed: {e2}", _render_doc_table(), gr.update()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_author(s: str) -> str:
    if not s or s == "Unknown": return "-"
    first = re.split(r",|\band\b", s, maxsplit=1)[0].strip()
    return first[:25] if first else "-"


PAGE_SIZE = 5


def _render_doc_table(page: int = 1) -> str:
    docs = get_all_documents()
    if not docs:
        return "No PDFs indexed yet."
    total       = len(docs)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * PAGE_SIZE
    page_docs   = docs[start: start + PAGE_SIZE]
    lines = [
        f"**Page {page} of {total_pages}** ({total} PDFs total)\n",
        "| # | Title | First Author | Pages | Chunks | Uploaded | Doc ID |",
        "|---|-------|-------------|-------|--------|----------|--------|",
    ]
    for i, d in enumerate(page_docs, start + 1):
        meta   = d.get("pdf_metadata") or {}
        title  = (meta.get("title") or d["filename"])[:40]
        author = _first_author(meta.get("authors", ""))
        lines.append(
            f"| {i} | {title} | {author} | {d['page_count']} | {d['chunk_count']} "
            f"| {d['uploaded_at'][:19].replace('T',' ')} | `{d['doc_id']}` |"
        )
    return "\n".join(lines)


def _render_doc_dataframe(page: int = 1) -> pd.DataFrame:
    docs = get_all_documents()
    if not docs:
        return pd.DataFrame(columns=["#", "Title", "First Author", "Pages", "Chunks", "Uploaded", "Doc ID"])

    total       = len(docs)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page        = max(1, min(page, total_pages))
    start       = (page - 1) * PAGE_SIZE
    page_docs   = docs[start: start + PAGE_SIZE]

    rows = []
    for i, d in enumerate(page_docs, start + 1):
        meta   = d.get("pdf_metadata") or {}
        title  = (meta.get("title") or d["filename"])[:45]
        author = _first_author(meta.get("authors", ""))
        rows.append({
            "#":            i,
            "Title":        title,
            "First Author": author,
            "Pages":        d["page_count"],
            "Chunks":       d["chunk_count"],
            "Uploaded":     d["uploaded_at"][:16].replace("T", " "),
            "Doc ID":       d["doc_id"],
        })
    return pd.DataFrame(rows)


def _total_pages() -> int:
    total = len(get_all_documents())
    return max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)


def refresh_doc_table():
    return _render_doc_table(1)


def go_prev_page(current_page: int):
    page = max(1, current_page - 1)
    return _render_doc_dataframe(page), page


def go_next_page(current_page: int):
    page = min(_total_pages(), current_page + 1)
    return _render_doc_dataframe(page), page


def on_row_select(evt: gr.SelectData, df: pd.DataFrame) -> str:
    try:
        row_idx = evt.index[0]
        doc_id  = df.iloc[row_idx]["Doc ID"]
        return str(doc_id)
    except Exception:
        return ""


def delete_selected(doc_id: str, current_page: int):
    if not doc_id or not doc_id.strip():
        return "Click a row in the table to select a paper first.", _render_doc_dataframe(current_page), gr.update(), current_page, ""
    status, _, scope = delete_pdf(doc_id.strip())
    new_df = _render_doc_dataframe(1)
    new_choices = gr.update(choices=_delete_choices(), value=None)
    return status, new_df, scope, 1, ""


def search_abstracts(query: str):
    if not query or not query.strip():
        return _render_doc_dataframe(1), 1, ""

    q    = query.lower().strip()
    docs = get_all_documents()
    hits = [d for d in docs if
            q in (d.get("pdf_metadata") or {}).get("title", "").lower() or
            q in (d.get("pdf_metadata") or {}).get("abstract", "").lower() or
            q in (d.get("pdf_summary") or "").lower()]

    if not hits:
        return _render_doc_dataframe(1), 1, f"No papers found matching '{query}'."

    rows = []
    for i, d in enumerate(hits, 1):
        meta   = d.get("pdf_metadata") or {}
        title  = (meta.get("title") or d["filename"])[:45]
        author = _first_author(meta.get("authors", ""))
        rows.append({
            "#":            i,
            "Title":        title,
            "First Author": author,
            "Pages":        d["page_count"],
            "Chunks":       d["chunk_count"],
            "Uploaded":     d["uploaded_at"][:16].replace("T", " "),
            "Doc ID":       d["doc_id"],
        })

    return (
        pd.DataFrame(rows),
        1,
        f"{len(hits)} result(s) for '{query}' - click Refresh to show all.",
    )


def _format_sources(sources: list) -> str:
    if not sources:
        return ""
    lines = []
    for i, s in enumerate(sources, 1):
        meta      = s.get("metadata", {})
        page      = meta.get("page", "?")
        pdf       = meta.get("pdf", "unknown")
        doc_type  = s.get("type", "text").upper()
        type_icon = "[IMG]" if doc_type == "IMAGE" else "[TXT]"
        preview   = s["text"][:80].replace("\n", " ").strip()
        lines.append(f"[{i}] {type_icon} {pdf} p.{page} — {preview}...")

    inner = "\n".join(lines)
    return f"\n\n---\nSources:\n{inner}"


def _find_image_in_sources(sources: list):
    """
    Scan retrieved source chunks for a saved figure image on disk.
    Image-type chunks checked first, text chunks as fallback.
    Returns (image_path, label) or (None, "").
    """
    for source in sources:
        if source.get("type") == "image":
            image_path = source.get("metadata", {}).get("image_path")
            if image_path and os.path.exists(image_path):
                meta  = source.get("metadata", {})
                label = f"Referenced figure - {meta.get('pdf', '?')} p.{meta.get('page', '?')}"
                return image_path, label

    for source in sources:
        image_path = source.get("metadata", {}).get("image_path")
        if image_path and os.path.exists(image_path):
            meta  = source.get("metadata", {})
            label = f"Referenced page - {meta.get('pdf', '?')} p.{meta.get('page', '?')}"
            return image_path, label

    return None, ""


def _scope_choices() -> list:
    docs = get_all_documents()
    choices = ["All PDFs"]
    for d in docs:
        meta  = d.get("pdf_metadata") or {}
        label = (meta.get("title") or d["filename"])[:40]
        choices.append(f"{label} ({d['doc_id'][:8]}...)")
    return choices


def _doc_id_from_choice(choice: str):
    if choice == "All PDFs" or not choice:
        return None
    m = re.search(r'\(([a-f0-9\-]{8})', choice)
    if m:
        prefix = m.group(1)
        for d in get_all_documents():
            if d["doc_id"].startswith(prefix):
                return d["doc_id"]
    return None


def _scope_label_from_choice(choice: str) -> str:
    if choice == "All PDFs" or not choice:
        return "All PDFs"
    doc_id = _doc_id_from_choice(choice)
    if doc_id:
        doc = get_document(doc_id)
        if doc:
            meta = doc.get("pdf_metadata") or {}
            return meta.get("title") or doc.get("filename", choice)
    return choice


def _paper_choices() -> list:
    return [
        f"{(d.get('pdf_metadata') or {}).get('title') or d['filename']} ({d['doc_id'][:8]}...)"
        for d in get_all_documents()
    ]


def _doc_ids_from_choices(choices):
    result = []
    for c in choices:
        did = _doc_id_from_choice(c)
        if did:
            result.append(did)
    return result


# ---------------------------------------------------------------------------
# Comparison handler
# ---------------------------------------------------------------------------

def run_comparison(query: str, paper1: str, paper2: str, paper3: str):
    selected = [p for p in [paper1, paper2, paper3] if p and p != "-"]
    if len(selected) < 2:
        return "Please select at least 2 papers.", ""
    doc_ids = _doc_ids_from_choices(selected)
    if len(doc_ids) < 2:
        return "Could not resolve selected papers.", ""
    answer, sources = ask_comparison(query, doc_ids)
    return answer, _format_sources(sources)


def _delete_choices() -> list:
    docs = get_all_documents()
    choices = []
    for d in docs:
        meta  = d.get("pdf_metadata") or {}
        label = (meta.get("title") or d["filename"])[:50]
        choices.append(f"{label}  [{d['doc_id'][:8]}]")
    return choices


def _doc_id_from_delete_choice(choice: str):
    if not choice:
        return None
    m = re.search(r'\[([a-f0-9\-]{8})\]', choice)
    if m:
        prefix = m.group(1)
        for d in get_all_documents():
            if d["doc_id"].startswith(prefix):
                return d["doc_id"]
    return None


def delete_by_dropdown(choice: str):
    if not choice:
        return "Please select a paper to delete.", _render_doc_table(1), gr.update(), 1, gr.update()
    doc_id = _doc_id_from_delete_choice(choice)
    if not doc_id:
        return "Could not resolve selection.", _render_doc_table(1), gr.update(), 1, gr.update()
    status, table, scope = delete_pdf(doc_id)
    new_choices = gr.update(choices=_delete_choices(), value=None)
    return status, _render_doc_table(1), scope, 1, new_choices


# ---------------------------------------------------------------------------
# CSS loader
# ---------------------------------------------------------------------------

def _load_css() -> str:
    css_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "style.css")
    try:
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print("[WARN]  style.css not found - running without custom styles.")
        return ""


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

def build_ui():
    with gr.Blocks(
        title="Multi-PDF RAG Assistant",
        theme=gr.themes.Base(
            primary_hue=gr.themes.colors.indigo,
            font=gr.themes.GoogleFont("Inter"),
        ),
        css=_load_css(),
    ) as app:

        gr.HTML("""
            <div class="app-header">
                <h1>Multi-PDF RAG Assistant</h1>
                <p>Upload PDFs and ask questions across all or scoped to one.</p>
            </div>
        """)

        scope_dropdown = gr.Dropdown(
            choices=_scope_choices(), value="All PDFs",
            label="Search scope", interactive=True,
        )

        # ── Chat tab ─────────────────────────────────────────────────────
        # Version-safe Chatbot: detect what the installed Gradio supports
        # at runtime so this file works on any Gradio version without changes.
        with gr.Tab("Chat"):

            import inspect as _inspect
            _chatbot_params = set(_inspect.signature(gr.Chatbot.__init__).parameters)
            _use_messages   = "type" in _chatbot_params          # Gradio >= 4.x
            _chatbot_kwargs = {"label": "", "height": 500}
            if _use_messages:
                _chatbot_kwargs["type"] = "messages"

            chatbot = gr.Chatbot(**_chatbot_kwargs)

            with gr.Row():
                chat_input = gr.Textbox(
                    placeholder="Ask a question about your PDFs...",
                    show_label=False,
                    scale=8,
                )
                send_btn = gr.Button("Send", variant="primary", scale=1)

            # Figure viewer — hidden until a source chunk has image_path on disk
            source_image = gr.Image(
                label="Referenced figure",
                visible=False,
                height=420,
            )

            gr.Examples(
                examples=[
                    "What is the main contribution of this paper?",
                    "What datasets were used?",
                    "What were the key accuracy results?",
                    "Explain any figures or diagrams.",
                    "Compare the methods described across papers.",
                ],
                inputs=chat_input,
            )

            # ── chat handler ─────────────────────────────────────────────
            # _use_messages captured above — True means dict format,
            # False means (user, assistant) tuple format.
            def handle_chat(query, history, scope_choice, request: gr.Request,
                            _msgs=_use_messages):
                history = history or []

                def _append_assistant(msg):
                    if _msgs:
                        history.append({"role": "assistant", "content": msg})
                    else:
                        history.append((None, msg))

                if get_index() is None:
                    _append_assistant("Please upload at least one PDF first.")
                    return history, gr.update(visible=False), ""

                session_id = str(request.session_hash) if request else "default"
                if not _check_rate_limit(session_id):
                    _append_assistant(
                        f"Rate limit reached ({MAX_REQUESTS_PER_MINUTE} req/min). Wait a moment."
                    )
                    return history, gr.update(visible=False), ""

                doc_id      = _doc_id_from_choice(scope_choice)
                scope_label = _scope_label_from_choice(scope_choice)

                try:
                    answer, sources, suggestions, _ = ask_question(query, doc_id=doc_id)
                    save_question(query, answer, scope_label)

                    full_answer = answer + _format_sources(sources)
                    if _msgs:
                        history.append({"role": "user",      "content": query})
                        history.append({"role": "assistant", "content": full_answer})
                    else:
                        history.append((query, full_answer))

                    # Show figure if any source chunk has a saved image on disk
                    image_path, image_label = _find_image_in_sources(sources)
                    if image_path:
                        image_update = gr.update(
                            value=image_path,
                            visible=True,
                            label=image_label,
                        )
                    else:
                        image_update = gr.update(visible=False)

                    return history, image_update, ""

                except Exception as e:
                    log.error("Query failed: %s", e)
                    _append_assistant(f"Something went wrong: {e}")
                    return history, gr.update(visible=False), ""

            send_btn.click(
                handle_chat,
                inputs=[chat_input, chatbot, scope_dropdown],
                outputs=[chatbot, source_image, chat_input],
            )
            chat_input.submit(
                handle_chat,
                inputs=[chat_input, chatbot, scope_dropdown],
                outputs=[chatbot, source_image, chat_input],
            )

        # ── Upload tab ───────────────────────────────────────────────────
        with gr.Tab("Upload PDF"):
            gr.Markdown("Upload one or multiple PDFs at once.")
            pdf_input     = gr.File(label="Upload PDF(s)", file_types=[".pdf"], file_count="multiple")
            upload_status = gr.Textbox(label="Upload Status", interactive=False, lines=8)
            pdf_input.change(process_pdfs, inputs=pdf_input, outputs=[upload_status, scope_dropdown])

        # ── Manage tab ───────────────────────────────────────────────────
        with gr.Tab("Manage PDFs"):
            gr.Markdown("### Search Papers")
            with gr.Row():
                search_box = gr.Textbox(placeholder="Search by title, abstract, or summary...", label="", scale=8)
                search_btn = gr.Button("Search", scale=1)
            search_status = gr.Markdown("")

            gr.Markdown("### Indexed Documents")
            gr.Markdown("*Click any row to select it, then click Delete Selected.*")

            doc_table_manage = gr.Dataframe(
                value=_render_doc_dataframe(1),
                interactive=False,
                wrap=True,
            )
            page_state      = gr.State(1)
            selected_doc_id = gr.State("")

            with gr.Row():
                prev_btn    = gr.Button("Prev", size="sm")
                refresh_btn = gr.Button("Refresh")
                next_btn    = gr.Button("Next", size="sm")

            search_btn.click(
                search_abstracts,
                inputs=search_box,
                outputs=[doc_table_manage, page_state, search_status],
            )
            search_box.submit(
                search_abstracts,
                inputs=search_box,
                outputs=[doc_table_manage, page_state, search_status],
            )
            refresh_btn.click(
                lambda: (_render_doc_dataframe(1), 1, ""),
                outputs=[doc_table_manage, page_state, search_status],
            )
            prev_btn.click(go_prev_page, inputs=[page_state], outputs=[doc_table_manage, page_state])
            next_btn.click(go_next_page, inputs=[page_state], outputs=[doc_table_manage, page_state])

            selected_label = gr.Textbox(label="Selected", interactive=False, lines=1, max_lines=1)

            doc_table_manage.select(
                on_row_select,
                inputs=[doc_table_manage],
                outputs=[selected_doc_id],
            )
            selected_doc_id.change(
                lambda did: f"Selected: {did}..." if did else "No paper selected - click a row above",
                inputs=[selected_doc_id],
                outputs=[selected_label],
            )

            with gr.Row():
                delete_btn = gr.Button("Delete Selected", variant="stop")
            delete_status = gr.Textbox(label="Delete Status", interactive=False)
            delete_btn.click(
                delete_selected,
                inputs=[selected_doc_id, page_state],
                outputs=[delete_status, doc_table_manage, scope_dropdown, page_state, selected_doc_id],
            )

            gr.Markdown("### Paper Details")
            docs = get_all_documents()
            if docs:
                for d in docs:
                    meta     = d.get("pdf_metadata") or {}
                    title    = meta.get("title") or d["filename"]
                    abstract = meta.get("abstract") or "Abstract not available."
                    summary  = d.get("pdf_summary") or "Summary not yet generated."
                    with gr.Accordion(label=title, open=False):
                        gr.Markdown(f"**Abstract**\n\n{abstract}\n\n---\n**Summary**\n\n{summary}")
            else:
                gr.Markdown("No papers indexed yet.")

        # ── Compare tab ──────────────────────────────────────────────────
        with gr.Tab("Compare Papers"):
            gr.Markdown("### Compare Papers Side by Side")
            gr.Markdown("Select 2 or 3 papers and ask a comparison question.")
            paper_opts = ["-"] + _paper_choices()
            with gr.Row():
                paper1_dd = gr.Dropdown(choices=paper_opts, value="-", label="Paper 1")
                paper2_dd = gr.Dropdown(choices=paper_opts, value="-", label="Paper 2")
                paper3_dd = gr.Dropdown(choices=paper_opts, value="-", label="Paper 3 (optional)")
            compare_query   = gr.Textbox(label="Comparison question", placeholder="e.g. How do the methods differ?", lines=2)
            compare_btn     = gr.Button("Compare", variant="primary")
            compare_answer  = gr.Markdown("")
            compare_sources = gr.Markdown("")
            compare_btn.click(
                run_comparison,
                inputs=[compare_query, paper1_dd, paper2_dd, paper3_dd],
                outputs=[compare_answer, compare_sources],
            )

        # ── Eval tab ─────────────────────────────────────────────────────
        with gr.Tab("Eval"):
            gr.Markdown("## RAG Evaluation Dashboard")
            gr.Markdown(
                "Score your recent chat queries across Faithfulness, "
                "Answer Relevancy, and Context Recall using a judge LLM "
                "(llama-3.3-70b). Scores are stored in SQLite and shown below."
            )

            with gr.Row():
                n_queries_slider = gr.Slider(
                    minimum=1, maximum=20, value=5, step=1,
                    label="Queries to score (most recent un-scored)",
                )
                score_btn = gr.Button("Score Now", variant="primary")

            eval_status = gr.Textbox(
                label="Scoring status", interactive=False, lines=4
            )

            gr.Markdown("---")
            gr.Markdown("### Summary")

            with gr.Row():
                faith_metric  = gr.Number(label="Avg Faithfulness",   precision=3)
                rel_metric    = gr.Number(label="Avg Relevancy",      precision=3)
                recall_metric = gr.Number(label="Avg Context Recall", precision=3)
                total_metric  = gr.Number(label="Total Scored",       precision=0)

            gr.Markdown("### Score history")
            scores_table = gr.Dataframe(
                headers=["Query", "Faithfulness", "Relevancy",
                         "Context Recall", "Reasoning", "Scope", "Scored At"],
                interactive=False,
                wrap=True,
            )

            gr.Markdown("### Failure analysis - lowest scoring answers")
            gr.Markdown(
                "Rows where any score < 0.5. "
                "Click a row to see the retrieved chunks that caused the failure."
            )
            failures_table = gr.Dataframe(
                headers=["Query", "Faithfulness", "Relevancy",
                         "Context Recall", "Reasoning"],
                interactive=False,
                wrap=True,
            )

            chunk_viewer = gr.Textbox(
                label="Retrieved chunks for selected row",
                interactive=False,
                lines=8,
            )

            clear_btn = gr.Button("Clear all eval scores", variant="stop")

            # ── helpers ──────────────────────────────────────────────────

            def _scores_to_df(rows):
                if not rows:
                    return pd.DataFrame(
                        columns=["Query", "Faithfulness", "Relevancy",
                                 "Context Recall", "Reasoning", "Scope", "Scored At"]
                    )
                return pd.DataFrame([{
                    "Query":          r["query"][:60],
                    "Faithfulness":   r["faithfulness"],
                    "Relevancy":      r["relevancy"],
                    "Context Recall": r["context_recall"],
                    "Reasoning":      r["reasoning"],
                    "Scope":          r["scope"],
                    "Scored At":      r["scored_at"][:16].replace("T", " "),
                } for r in rows])

            def _failures_to_df(rows):
                fails = [r for r in rows if
                         (r["faithfulness"]   or 1) < 0.5 or
                         (r["relevancy"]      or 1) < 0.5 or
                         (r["context_recall"] or 1) < 0.5]
                if not fails:
                    return pd.DataFrame(
                        columns=["Query", "Faithfulness", "Relevancy",
                                 "Context Recall", "Reasoning"]
                    )
                return pd.DataFrame([{
                    "Query":          r["query"][:80],
                    "Faithfulness":   r["faithfulness"],
                    "Relevancy":      r["relevancy"],
                    "Context Recall": r["context_recall"],
                    "Reasoning":      r["reasoning"],
                } for r in fails])

            def _refresh_dashboard():
                from pipeline.db import get_eval_scores, get_eval_summary
                rows    = get_eval_scores(limit=200)
                summary = get_eval_summary()
                return (
                    _scores_to_df(rows),
                    _failures_to_df(rows),
                    summary["avg_faithfulness"],
                    summary["avg_relevancy"],
                    summary["avg_context_recall"],
                    summary["total"],
                )

            def run_scoring(n: int):
                from eval.run_eval import run_on_recent_queries
                yield "Scoring in progress - this may take 1-2 min on free tier..."
                try:
                    results = run_on_recent_queries(n=int(n))
                    if not results:
                        yield ("No un-scored queries found. "
                               "Chat with your PDFs first, then come back here.")
                    else:
                        scored = [r for r in results if r.get("faithfulness", -1) >= 0]
                        failed = len(results) - len(scored)
                        msg = f"Scored {len(scored)} queries."
                        if failed:
                            msg += f" ({failed} failed - likely rate limit, try again.)"
                        yield msg
                except Exception as e:
                    yield f"Scoring failed: {e}"

            def show_chunks_for_row(evt: gr.SelectData, failures_df):
                try:
                    row_idx = evt.index[0]
                    query   = failures_df.iloc[row_idx]["Query"]
                    from pipeline.db import get_eval_scores
                    rows  = get_eval_scores(limit=200)
                    match = next((r for r in rows if r["query"].startswith(query[:40])), None)
                    if not match:
                        return "No chunk data found for this row."
                    chunks = match.get("chunks", [])
                    if not chunks:
                        return "No chunks stored for this query."
                    lines = [f"[Chunk {i+1}]:\n{c[:400]}\n" for i, c in enumerate(chunks)]
                    return "\n---\n".join(lines)
                except Exception as e:
                    return f"Error: {e}"

            def clear_scores():
                from pipeline.db import clear_eval_scores
                clear_eval_scores()
                return ("Cleared.", *_refresh_dashboard())

            # ── wire up ──────────────────────────────────────────────────

            score_btn.click(
                run_scoring,
                inputs=[n_queries_slider],
                outputs=[eval_status],
            ).then(
                _refresh_dashboard,
                outputs=[scores_table, failures_table,
                         faith_metric, rel_metric, recall_metric, total_metric],
            )

            clear_btn.click(
                clear_scores,
                outputs=[eval_status, scores_table, failures_table,
                         faith_metric, rel_metric, recall_metric, total_metric],
            )

            failures_table.select(
                show_chunks_for_row,
                inputs=[failures_table],
                outputs=[chunk_viewer],
            )

            app.load(
                _refresh_dashboard,
                outputs=[scores_table, failures_table,
                         faith_metric, rel_metric, recall_metric, total_metric],
            )

    return app