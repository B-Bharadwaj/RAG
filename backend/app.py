"""
streamlit_app.py - AI Business Report Analyzer v2
===================================================
Mode switcher at the top:
     PDF Mode  - full v1 RAG pipeline (Chat, Upload, Manage, Compare, Eval)
     Data Mode - v2 business pipeline (Upload, Chat, Visualize, Report)

"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import re
import time
import tempfile
import pandas as pd
import streamlit as st
from collections import defaultdict
from pypdf import PdfReader
from pypdf.errors import PdfReadError

# -- v1 imports -------------------------------------------------------------
from pipeline.loader  import load_pdf, extract_images
from pipeline.ocr     import caption_images
from pipeline.indexer import add_to_index, get_index, load_state, remove_from_index
from pipeline.chunker import chunk_text_with_pages, create_documents, clean_documents
from pipeline.db      import (
    generate_doc_id, register_document, get_all_documents,
    delete_document, update_document_metadata, update_document_summary,
    filename_exists, save_question,
    get_eval_scores, get_eval_summary, clear_eval_scores,
    get_all_business_files, get_business_file, delete_business_file,
    get_document,
)
from generation.generator import (
    ask_question, reset_memory, extract_pdf_metadata,
    generate_paper_summary, ask_comparison, reset_business_memory,
)
from config import MAX_REQUESTS_PER_MINUTE

# -- v2 imports -------------------------------------------------------------
from services.analyzer        import (
    process_uploaded_file, answer_question,
    get_executive_summary, get_anomaly_explanation,
    get_cached_file, restore_file_from_disk,
)
from services.chart_generator  import generate_chart
from services.report_generator import generate_report

import styles

# -- Logger -----------------------------------------------------------------
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

MAX_FILE_SIZE_MB = 50
MAX_PAGE_COUNT   = 100

load_state()

# -- Page config ------------------------------------------------------------
st.set_page_config(
    page_title="RAG v2",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

styles.inject()

st.markdown("""
<style>
[data-testid="collapsedControl"] { display: none !important; }
[data-testid="stSidebar"]        { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# -- Session state ----------------------------------------------------------
defaults = {
    "mode":                "pdf",
    "pdf_chat_history":    [],
    "pdf_pending_query":   "",
    "rate_store":          defaultdict(lambda: (0, time.time())),
    "data_chat_history":   [],
    "data_pending_query":  "",
    "active_file_id":      None,
    "active_file_name":    None,
    "active_file_type":    None,
    "active_processed":    None,
    "exec_summary":        "",
    "anomaly_explanation": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.session_state.pdf_chat_history = [
    (t[0], t[1], [], t[2], t[3]) if len(t) == 4 else t
    for t in st.session_state.pdf_chat_history
]


# =============================================================================
# SHARED HELPERS
# =============================================================================

def _check_rate_limit() -> bool:
    sid = "default"
    count, t0 = st.session_state.rate_store[sid]
    now = time.time()
    if now - t0 > 60:
        st.session_state.rate_store[sid] = (1, now)
        return True
    if count >= MAX_REQUESTS_PER_MINUTE:
        return False
    st.session_state.rate_store[sid] = (count + 1, t0)
    return True


def _first_author(s: str) -> str:
    if not s or s == "Unknown":
        return "-"
    first = re.split(r",|\band\b", s, maxsplit=1)[0].strip()
    return first[:30] if first else "-"


def _find_image(sources: list):
    for s in sources:
        if s.get("type") == "image":
            p = s.get("metadata", {}).get("image_path")
            if p and os.path.exists(p):
                m = s["metadata"]
                return p, f"{m.get('pdf','?')} p.{m.get('page','?')}"
    return None, ""


def _score_badge(val) -> str:
    if val is None or val < 0:
        return "<span class='badge-r'>n/a</span>"
    if val >= 0.7:
        return f"<span class='badge-g'>{val:.2f}</span>"
    if val >= 0.5:
        return f"<span class='badge-m'>{val:.2f}</span>"
    return f"<span class='badge-r'>{val:.2f}</span>"


def _severity_emoji(s: str) -> str:
    return {"high": " ", "medium": " ", "low": " "}.get(s, " ")


def _validate_pdf(path: str, name: str) -> int:
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"'{name}' is {size_mb:.1f} MB - exceeds {MAX_FILE_SIZE_MB} MB.")
    try:
        n = len(PdfReader(path).pages)
    except PdfReadError as e:
        raise ValueError(f"Not a valid PDF: {e}")
    if n == 0:
        raise ValueError(f"'{name}' has no pages.")
    if n > MAX_PAGE_COUNT:
        raise ValueError(f"'{name}' has {n} pages - exceeds {MAX_PAGE_COUNT}.")
    return n


def _scope_options() -> list:
    opts = ["All PDFs"]
    for d in get_all_documents():
        meta  = d.get("pdf_metadata") or {}
        label = (meta.get("title") or d["filename"])[:45]
        opts.append(f"{label}  [{d['doc_id'][:8]}]")
    return opts


def _doc_id_from_label(label: str):
    if not label or label == "All PDFs":
        return None
    m = re.search(r'\[([a-f0-9\-]{8})\]', label)
    if m:
        prefix = m.group(1)
        for d in get_all_documents():
            if d["doc_id"].startswith(prefix):
                return d["doc_id"]
    return None


def _paper_options() -> list:
    return [
        f"{(d.get('pdf_metadata') or {}).get('title') or d['filename']}  [{d['doc_id'][:8]}]"
        for d in get_all_documents()
    ]


def _data_active_banner() -> bool:
    if not st.session_state.active_file_id:
        st.markdown("""
        <div class="empty-box">
            <div class="empty-icon"> </div>
            <div class="empty-title">No file loaded</div>
            <div class="empty-sub">Upload a file in the   Upload tab first</div>
        </div>""", unsafe_allow_html=True)
        return False
    ftype  = st.session_state.active_file_type or ""
    colors = {"csv": ("#14532d", "#4ade80"), "excel": ("#365314", "#a3e635")}
    bg, fg = colors.get(ftype, ("#1e3a5f", "#60a5fa"))
    badge  = (
        f"<span style='background:{bg};color:{fg};"
        f"padding:2px 10px;border-radius:20px;"
        f"font-size:0.72rem;font-weight:600;'>{ftype.upper()}</span>"
    )
    st.markdown(
        f"<p class='muted'>Active file: "
        f"<span style='color:#a5b4fc;font-weight:600;'>"
        f"{st.session_state.active_file_name}</span> &nbsp;{badge}</p>",
        unsafe_allow_html=True,
    )
    return True


def _set_active(file_id, file_name, file_type, processed=None):
    st.session_state.active_file_id     = file_id
    st.session_state.active_file_name   = file_name
    st.session_state.active_file_type   = file_type
    st.session_state.active_processed   = processed
    st.session_state.data_chat_history  = []
    st.session_state.exec_summary       = ""
    st.session_state.anomaly_explanation = ""


BIZ_EXAMPLES = [
    "Show me quantity by country",
    "What is the total revenue?",
    "Which country has highest sales?",
    "Distribution of unit price",
    "Top products by quantity",
    "Compare sales by country",
    "What are the key findings?",
    "Any data quality issues?",
]

PDF_EXAMPLES = [
    "What is the main contribution?",
    "What datasets were used?",
    "What were the key results?",
    "Explain the model architecture.",
    "What are the limitations?",
    "How does this compare to prior work?",
    "Summarise all paper abstracts.",
    "What future work is suggested?",
]


# =============================================================================
# TOP BAR + MODE SWITCHER
# =============================================================================

all_pdfs = get_all_documents()
all_biz  = get_all_business_files()
n_pdfs   = len(all_pdfs)
n_biz    = len(all_biz)

top_left, top_right = st.columns([3, 1])
with top_left:
    st.markdown(
        "<p style='font-size:1.1rem;font-weight:700;color:#ffffff;margin:0;'>"
        " AI Business Report Analyzer - v2</p>"
        "<p style='font-size:0.75rem;color:#6b7280;margin:2px 0 0;'>"
        "PDF   Excel   CSV - upload anything, ask anything</p>",
        unsafe_allow_html=True,
    )
with top_right:
    st.markdown(
        f"<p style='font-size:0.78rem;color:#6b7280;text-align:right;margin:0;'>"
        f"{n_pdfs} PDF{'s' if n_pdfs != 1 else ''}   "
        f"{n_biz} data file{'s' if n_biz != 1 else ''}</p>",
        unsafe_allow_html=True,
    )

st.markdown("<hr style='margin:10px 0 8px;border-color:#1f1f1f;'>", unsafe_allow_html=True)

# -- Mode switcher ----------------------------------------------------------
st.markdown("<p class='muted' style='margin-bottom:6px;'>Select mode</p>", unsafe_allow_html=True)
mode_col1, mode_col2, _ = st.columns([1, 1, 5])
with mode_col1:
    if st.button(
        " PDF Mode",
        use_container_width=True,
        type="primary" if st.session_state.mode == "pdf" else "secondary",
    ):
        st.session_state.mode = "pdf"
        st.rerun()
with mode_col2:
    if st.button(
        " Data Mode",
        use_container_width=True,
        type="primary" if st.session_state.mode == "data" else "secondary",
    ):
        st.session_state.mode = "data"
        st.rerun()

st.markdown("<hr style='margin:8px 0 4px;border-color:#1f1f1f;'>", unsafe_allow_html=True)


# =============================================================================
# PDF MODE
# =============================================================================

if st.session_state.mode == "pdf":

    tab_chat, tab_upload, tab_manage, tab_compare, tab_eval = st.tabs([
        "  Chat", "  Upload", "   Manage", "  Compare", " Eval",
    ])

    # -- CHAT ------------------------------------------------------------------
    with tab_chat:
        ctrl_left, ctrl_mid, ctrl_right = st.columns([3, 1, 1])
        with ctrl_left:
            scope_opts  = _scope_options()
            scope_label = st.selectbox("Search scope", scope_opts, label_visibility="collapsed")
        with ctrl_mid:
            is_all     = scope_label == "All PDFs"
            badge_text = "All PDFs" if is_all else scope_label.split("[")[0].strip()[:20]
            st.markdown(
                f"<span style='background:#1e2535;color:#a5b4fc;"
                f"padding:3px 10px;border-radius:12px;"
                f"font-size:0.74rem;font-weight:500;'>{badge_text}</span>",
                unsafe_allow_html=True,
            )
        with ctrl_right:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Clear memory", use_container_width=True):
                reset_memory()
                st.session_state.pdf_chat_history = []
                st.rerun()

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown("<p class='muted' style='margin-bottom:6px;'>Try asking</p>", unsafe_allow_html=True)
        chip_cols = st.columns(4)
        for idx, ex in enumerate(PDF_EXAMPLES):
            with chip_cols[idx % 4]:
                if st.button(ex, key=f"pdf_chip_{idx}", use_container_width=True):
                    st.session_state.pdf_pending_query = ex
                    st.rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        history = st.session_state.pdf_chat_history
        if not history:
            st.markdown("""
            <div class="empty-box">
                <div class="empty-icon"> </div>
                <div class="empty-title">Ask a question about your research papers</div>
                <div class="empty-sub">Upload PDFs in the Upload tab first</div>
            </div>""", unsafe_allow_html=True)
        else:
            for turn in history:
                if len(turn) == 4:
                    q, a, img_path, img_label = turn
                    sources = []
                else:
                    q, a, sources, img_path, img_label = turn
                with st.chat_message("user", avatar=" "):
                    st.markdown(q)
                with st.chat_message("assistant", avatar=" "):
                    st.markdown(a)
                    if sources:
                        with st.expander(f"  Sources ({len(sources)})", expanded=False):
                            for i, s in enumerate(sources, 1):
                                meta    = s.get("metadata", {})
                                icon    = "  " if s.get("type") == "image" else ""
                                preview = s["text"][:150].replace("\n", " ").strip()
                                st.markdown(
                                    f"**[{i}]** {icon} `{meta.get('pdf','?')}`"
                                    f" p.{meta.get('page','?')}\n\n> {preview}..."
                                )
                    if img_path and os.path.exists(img_path):
                        st.image(img_path, caption=img_label, width=400)

        with st.form("pdf_chat_form", clear_on_submit=True):
            col_in, col_btn = st.columns([10, 1])
            with col_in:
                user_query = st.text_input(
                    "q", value=st.session_state.pdf_pending_query,
                    placeholder="Ask anything about your papers...",
                    label_visibility="collapsed",
                )
            with col_btn:
                submitted = st.form_submit_button("Send", use_container_width=True)

        query_to_run = user_query.strip() or st.session_state.pdf_pending_query.strip()

        if submitted and query_to_run:
            st.session_state.pdf_pending_query = ""
            if get_index() is None:
                st.error("Index not loaded. Upload PDFs first.")
            elif not _check_rate_limit():
                st.warning(f"Rate limit reached ({MAX_REQUESTS_PER_MINUTE} req/min). Wait a moment.")
            else:
                doc_id     = _doc_id_from_label(scope_label)
                scope_name = scope_label.split("[")[0].strip() if "[" in scope_label else scope_label
                with st.spinner("Thinking..."):
                    try:
                        answer, sources, _, _ = ask_question(query_to_run, doc_id=doc_id)
                        save_question(query_to_run, answer, scope_name)
                        img_path, img_label = _find_image(sources)
                        st.session_state.pdf_chat_history.append(
                            (query_to_run, answer, sources, img_path, img_label)
                        )
                        st.rerun()
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")

    # -- UPLOAD ----------------------------------------------------------------
    with tab_upload:
        st.markdown("<p class='sec-title'>Upload Research Papers</p>", unsafe_allow_html=True)
        st.markdown(
            "<p class='muted'>Supports multiple PDFs. Each is validated, "
            "OCR'd with Groq Vision, chunked, and indexed.</p>",
            unsafe_allow_html=True,
        )

        uploaded_files = st.file_uploader(
            "drop", type=["pdf"], accept_multiple_files=True, label_visibility="collapsed"
        )

        if uploaded_files and st.button("Process PDFs", type="primary"):
            total    = len(uploaded_files)
            prog_bar = st.progress(0, text="Starting...")
            log_area = st.empty()
            lines    = []

            def _log(msg: str):
                lines.append(msg)
                log_area.markdown(
                    f"<div class='log-term'>{'<br>'.join(lines[-14:])}</div>",
                    unsafe_allow_html=True,
                )

            for idx, uf in enumerate(uploaded_files):
                name = uf.name
                prog_bar.progress(idx / total, text=f"[{idx+1}/{total}] {name}")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uf.read())
                    tmp_path = tmp.name

                try:
                    page_count = _validate_pdf(tmp_path, name)
                except ValueError as e:
                    _log(f"WARN  {e}")
                    os.unlink(tmp_path)
                    continue

                if filename_exists(name):
                    _log(f"SKIP  '{name}' already indexed.")
                    os.unlink(tmp_path)
                    continue

                doc_id = generate_doc_id()
                try:
                    _log(f"TEXT  Extracting text - {name}")
                    pages_text = load_pdf(tmp_path)
                    chunks     = chunk_text_with_pages(pages_text)
                    text_docs  = create_documents(chunks, name, doc_id)
                    _log(f"IMG   Rendering {page_count} pages...")
                    images     = extract_images(tmp_path)
                    _log("OCR   Captioning with Groq Vision...")
                    image_docs = caption_images(images, name, doc_id, pdf_path=tmp_path)
                    _log(f"IDX   Encoding {len(text_docs + image_docs)} chunks...")
                    all_docs   = clean_documents(text_docs + image_docs)
                    add_to_index(all_docs)
                    register_document(doc_id, name, page_count, len(all_docs))
                    _log("META  Extracting metadata...")
                    first_page_text = pages_text[0][1] if pages_text else ""
                    meta = extract_pdf_metadata(first_page_text, name)
                    update_document_metadata(doc_id, meta)
                    _log("SUM   Generating summary...")
                    summary = generate_paper_summary(doc_id, name)
                    if summary:
                        update_document_summary(doc_id, summary)
                    _log(f"DONE  '{meta.get('title', name)}' - {len(all_docs)} chunks")
                except Exception as e:
                    _log(f"ERR   {name} - {e}")
                finally:
                    os.unlink(tmp_path)

                prog_bar.progress((idx + 1) / total, text=f"[{idx+1}/{total}] Done")

            prog_bar.progress(1.0, text="All done!")
            st.success("Done! Switch to the Chat tab to start asking questions.")
            st.rerun()

    # -- MANAGE ----------------------------------------------------------------
    with tab_manage:
        st.markdown("<p class='sec-title'>Indexed Documents</p>", unsafe_allow_html=True)
        manage_docs = get_all_documents()

        if not manage_docs:
            st.markdown("""
            <div class="empty-box">
                <div class="empty-icon"> </div>
                <div class="empty-title">No PDFs indexed yet</div>
                <div class="empty-sub">Go to the Upload tab to add research papers</div>
            </div>""", unsafe_allow_html=True)
        else:
            total_chunks = sum(d["chunk_count"] for d in manage_docs)
            total_pages  = sum(d["page_count"]  for d in manage_docs)
            st.markdown(f"""
            <div class="kpi-grid">
              <div class="kpi-item"><span class="kpi-label">Papers indexed</span>
                <span class="kpi-sm">{len(manage_docs)}</span></div>
              <div class="kpi-item"><span class="kpi-label">Total pages</span>
                <span class="kpi-sm">{total_pages:,}</span></div>
              <div class="kpi-item"><span class="kpi-label">Total chunks</span>
                <span class="kpi-sm">{total_chunks:,}</span></div>
            </div>""", unsafe_allow_html=True)
            st.markdown("---")

            search_q = st.text_input(
                "search", placeholder="Filter by title, abstract, or summary...",
                label_visibility="collapsed",
            )
            filtered = manage_docs
            if search_q.strip():
                q = search_q.lower()
                filtered = [
                    d for d in manage_docs
                    if q in (d.get("pdf_metadata") or {}).get("title", "").lower()
                    or q in (d.get("pdf_metadata") or {}).get("abstract", "").lower()
                    or q in (d.get("pdf_summary") or "").lower()
                ]
                st.markdown(
                    f"<p class='muted'>{len(filtered)} of {len(manage_docs)} match</p>",
                    unsafe_allow_html=True,
                )

            hcols = st.columns([4, 2, 1, 1, 2, 1])
            for hc, h in zip(hcols, ["Title", "First Author", "Pages", "Chunks", "Uploaded", ""]):
                hc.markdown(
                    f"<p style='font-size:0.72rem;font-weight:600;color:#6b7280;"
                    f"text-transform:uppercase;letter-spacing:0.05em;margin:0;'>{h}</p>",
                    unsafe_allow_html=True,
                )
            st.markdown("<hr style='margin:6px 0;border-color:#1f1f1f;'>", unsafe_allow_html=True)

            delete_target = None
            for d in filtered:
                meta     = d.get("pdf_metadata") or {}
                title    = (meta.get("title") or d["filename"])[:50]
                author   = _first_author(meta.get("authors", ""))
                pages    = d["page_count"]
                chunks   = d["chunk_count"]
                uploaded = d["uploaded_at"][:16].replace("T", " ")
                doc_id   = d["doc_id"]
                rc = st.columns([4, 2, 1, 1, 2, 1])
                rc[0].markdown(f"<p style='font-size:0.85rem;color:#e5e5e5;margin:0;'>{title}</p>", unsafe_allow_html=True)
                rc[1].markdown(f"<p style='font-size:0.83rem;color:#9ca3af;margin:0;'>{author}</p>", unsafe_allow_html=True)
                rc[2].markdown(f"<p style='font-size:0.83rem;color:#9ca3af;margin:0;'>{pages}</p>", unsafe_allow_html=True)
                rc[3].markdown(f"<p style='font-size:0.83rem;color:#9ca3af;margin:0;'>{chunks}</p>", unsafe_allow_html=True)
                rc[4].markdown(f"<p style='font-size:0.83rem;color:#6b7280;margin:0;'>{uploaded}</p>", unsafe_allow_html=True)
                if rc[5].button("  ", key=f"del_{doc_id}"):
                    delete_target = d
                st.markdown("<hr style='margin:4px 0;border-color:#1a1a1a;'>", unsafe_allow_html=True)

            if delete_target:
                with st.spinner(f"Deleting '{delete_target['filename']}'..."):
                    try:
                        remove_from_index(delete_target["doc_id"])
                        delete_document(delete_target["doc_id"])
                        reset_memory()
                        images_dir = os.path.join("storage", "images")
                        if os.path.exists(images_dir):
                            for fname in os.listdir(images_dir):
                                if fname.startswith(delete_target["doc_id"]):
                                    try:
                                        os.remove(os.path.join(images_dir, fname))
                                    except Exception:
                                        pass
                        st.success(f"Deleted '{delete_target['filename']}'.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Delete failed: {e}")

            st.markdown("---")
            st.markdown("<p class='sec-title' style='font-size:0.9rem;'>Paper details</p>", unsafe_allow_html=True)
            for d in filtered:
                meta     = d.get("pdf_metadata") or {}
                title    = meta.get("title") or d["filename"]
                authors  = meta.get("authors") or "Unknown"
                abstract = meta.get("abstract") or "Abstract not available."
                summary  = d.get("pdf_summary") or "Summary not yet generated."
                with st.expander(title):
                    st.markdown(f"<p class='muted'>Authors: {authors}</p>", unsafe_allow_html=True)
                    st.markdown("**Abstract**")
                    st.markdown(abstract)
                    st.markdown("---")
                    st.markdown("**Auto-generated summary**")
                    st.markdown(summary)

    # -- COMPARE ---------------------------------------------------------------
    with tab_compare:
        st.markdown("<p class='sec-title'>Compare Papers Side by Side</p>", unsafe_allow_html=True)
        st.markdown("<p class='muted'>Select 2 or 3 papers and ask a comparison question.</p>", unsafe_allow_html=True)

        paper_opts = ["-- select --"] + _paper_options()
        col1, col2, col3 = st.columns(3)
        with col1:
            p1 = st.selectbox("Paper 1", paper_opts, key="cmp1")
        with col2:
            p2 = st.selectbox("Paper 2", paper_opts, key="cmp2")
        with col3:
            p3 = st.selectbox("Paper 3 (optional)", paper_opts, key="cmp3")

        compare_q = st.text_area("Comparison question", placeholder="e.g. How do the methods differ?", height=90)

        if st.button("Compare", type="primary"):
            selected = [p for p in [p1, p2, p3] if p and p != "-- select --"]
            if len(selected) < 2:
                st.warning("Please select at least 2 papers.")
            elif not compare_q.strip():
                st.warning("Please enter a comparison question.")
            else:
                doc_ids = []
                for sel in selected:
                    m = re.search(r'\[([a-f0-9\-]{8})\]', sel)
                    if m:
                        prefix = m.group(1)
                        for d in get_all_documents():
                            if d["doc_id"].startswith(prefix):
                                doc_ids.append(d["doc_id"])
                                break
                if len(doc_ids) < 2:
                    st.error("Could not resolve selected papers.")
                else:
                    with st.spinner("Comparing papers..."):
                        answer, sources = ask_comparison(compare_q, doc_ids)
                    with st.chat_message("assistant", avatar=" "):
                        st.markdown(answer)
                        if sources:
                            with st.expander(f"  Sources ({len(sources)})"):
                                for i, s in enumerate(sources, 1):
                                    meta    = s.get("metadata", {})
                                    icon    = "  " if s.get("type") == "image" else ""
                                    preview = s["text"][:150].replace("\n", " ").strip()
                                    st.markdown(
                                        f"**[{i}]** {icon} `{meta.get('pdf','?')}`"
                                        f" p.{meta.get('page','?')}\n\n> {preview}..."
                                    )

    # -- EVAL ------------------------------------------------------------------
    with tab_eval:
        st.markdown("<p class='sec-title'>RAG Evaluation Dashboard</p>", unsafe_allow_html=True)
        st.markdown(
            "<p class='muted'>Judge LLM (llama-3.3-70b) scores each response across "
            "Faithfulness, Answer Relevancy, and Context Recall.</p>",
            unsafe_allow_html=True,
        )

        col_s, col_b = st.columns([3, 1])
        with col_s:
            n_to_score = st.slider("Queries to score (most recent un-scored)", 1, 20, 5)
        with col_b:
            st.markdown("<br>", unsafe_allow_html=True)
            run_eval = st.button("Score Now", type="primary", use_container_width=True)

        if run_eval:
            from eval.run_eval import run_on_recent_queries
            with st.spinner("Scoring - may take 1-2 min on free tier..."):
                try:
                    results = run_on_recent_queries(n=n_to_score)
                    if not results:
                        st.warning("No un-scored queries found. Chat with your PDFs first.")
                    else:
                        scored = [r for r in results if r.get("faithfulness", -1) >= 0]
                        failed = len(results) - len(scored)
                        msg    = f"Scored {len(scored)} queries."
                        if failed:
                            msg += f" ({failed} failed - rate limit, try again.)"
                        st.success(msg)
                        st.rerun()
                except Exception as e:
                    st.error(f"Scoring failed: {e}")

        st.markdown("---")
        summary = get_eval_summary()
        st.markdown("<p class='sec-title'>KPIs</p>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="kpi-grid">
          <div class="kpi-item"><span class="kpi-label">Avg Faithfulness</span>
            <span class="kpi-value">{summary['avg_faithfulness']:.4f}</span></div>
          <div class="kpi-item"><span class="kpi-label">Avg Relevancy</span>
            <span class="kpi-value">{summary['avg_relevancy']:.4f}</span></div>
          <div class="kpi-item"><span class="kpi-label">Avg Context Recall</span>
            <span class="kpi-value">{summary['avg_context_recall']:.4f}</span></div>
          <div class="kpi-item"><span class="kpi-label">Total scored</span>
            <span class="kpi-value">{summary['total']}</span></div>
        </div>""", unsafe_allow_html=True)

        st.markdown("---")
        rows = get_eval_scores(limit=200)
        st.markdown("<p class='sec-title'>Score history</p>", unsafe_allow_html=True)
        if not rows:
            st.markdown("<p class='muted'>No scores yet. Click Score Now above.</p>", unsafe_allow_html=True)
        else:
            hist_df = pd.DataFrame([{
                "Query":          r["query"][:60],
                "Faithfulness":   round(r["faithfulness"] or 0, 3),
                "Relevancy":      round(r["relevancy"] or 0, 3),
                "Context Recall": round(r["context_recall"] or 0, 3),
                "Reasoning":      r["reasoning"],
                "Scope":          r["scope"],
                "Scored At":      r["scored_at"][:16].replace("T", " "),
            } for r in rows])
            st.dataframe(hist_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("<p class='sec-title'>Failure analysis</p>", unsafe_allow_html=True)
        st.markdown("<p class='muted'>Responses where any score is below 0.5.</p>", unsafe_allow_html=True)
        fails = [
            r for r in rows
            if (r["faithfulness"]   or 1) < 0.5
            or (r["relevancy"]      or 1) < 0.5
            or (r["context_recall"] or 1) < 0.5
        ]
        if not fails:
            st.markdown(
                "<p class='muted' style='color:#4ade80;'>No failures - all scores above 0.5.</p>",
                unsafe_allow_html=True,
            )
        else:
            for r in fails:
                with st.expander(r["query"][:80]):
                    st.markdown(
                        f"**Faithfulness** {_score_badge(r['faithfulness'])}&nbsp;&nbsp;"
                        f"**Relevancy** {_score_badge(r['relevancy'])}&nbsp;&nbsp;"
                        f"**Context Recall** {_score_badge(r['context_recall'])}",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Judge reasoning:** {r['reasoning']}")
                    for i, c in enumerate(r.get("chunks", []), 1):
                        st.markdown(
                            f"<div class='src-card'><b>Chunk {i}</b><br>{c[:400]}</div>",
                            unsafe_allow_html=True,
                        )
        st.markdown("---")
        if st.button("Clear all eval scores"):
            clear_eval_scores()
            st.success("Cleared.")
            st.rerun()


# =============================================================================
# DATA MODE
# =============================================================================

else:

    tab_upload, tab_chat, tab_viz, tab_report = st.tabs([
        "  Upload", "  Chat", "  Visualize", "  Report",
    ])

    # -- UPLOAD ----------------------------------------------------------------
    with tab_upload:
        st.markdown("<p class='sec-title'>Upload Business File</p>", unsafe_allow_html=True)
        st.markdown(
            "<p class='muted'>Supports Excel (.xlsx) and CSV (.csv). "
            "Data is processed locally - only statistical summaries are sent to the AI.</p>",
            unsafe_allow_html=True,
        )

        uploaded_file = st.file_uploader(
            "drop", type=["xlsx", "xls", "csv"], label_visibility="collapsed",
        )

        if uploaded_file and st.button("Process File", type="primary"):
            lines    = []
            log_area = st.empty()
            prog     = st.progress(0, text="Starting...")

            def _log_data(msg: str):
                lines.append(msg)
                log_area.markdown(
                    f"<div class='log-term'>{'<br>'.join(lines[-10:])}</div>",
                    unsafe_allow_html=True,
                )

            try:
                _log_data(f"READ  Reading {uploaded_file.name}...")
                prog.progress(20, text="Reading file...")
                file_bytes = uploaded_file.read()

                _log_data("PROC  Running Pandas analysis...")
                prog.progress(50, text="Analyzing data...")
                result = process_uploaded_file(
                    file_bytes=file_bytes,
                    file_name=uploaded_file.name,
                )

                prog.progress(80, text="Generating AI insights...")
                if result["status"] == "already_exists":
                    _log_data("SKIP  Already processed - loaded from cache")
                else:
                    _log_data(f"SHPE  {result['shape'][0]:,} rows   {result['shape'][1]} cols")
                    _log_data(f"ANOM  {len(result['anomalies'])} anomalies detected")
                    _log_data("AI    Insights generated")

                _set_active(result["file_id"], result["file_name"], result["file_type"], result)
                prog.progress(100, text="Done!")
                _log_data("DONE  Ready!")
                st.success(f"  '{uploaded_file.name}' processed - switch to Chat tab!")

                st.markdown(f"""
                <div class="kpi-grid" style="margin-top:1.2rem;">
                  <div class="kpi-item"><span class="kpi-label">Rows</span>
                    <span class="kpi-sm">{result['shape'][0]:,}</span></div>
                  <div class="kpi-item"><span class="kpi-label">Columns</span>
                    <span class="kpi-sm">{result['shape'][1]}</span></div>
                  <div class="kpi-item"><span class="kpi-label">Anomalies</span>
                    <span class="kpi-sm">{len(result['anomalies'])}</span></div>
                  <div class="kpi-item"><span class="kpi-label">Sheets</span>
                    <span class="kpi-sm">{len(result['sheet_names'])}</span></div>
                </div>""", unsafe_allow_html=True)

                if result.get("insights"):
                    st.markdown("---")
                    st.markdown("<p class='sec-title'>Auto-Generated Insights</p>", unsafe_allow_html=True)
                    st.markdown(result["insights"])

            except Exception as e:
                st.error(f"Processing failed: {e}")
                log.error("Data upload failed: %s", e)

        st.markdown("---")
        st.markdown("<p class='sec-title'>Previously Uploaded Files</p>", unsafe_allow_html=True)

        biz_files = get_all_business_files()
        if not biz_files:
            st.markdown("""
            <div class="empty-box">
                <div class="empty-icon"> </div>
                <div class="empty-title">No files uploaded yet</div>
                <div class="empty-sub">Upload an Excel or CSV file above</div>
            </div>""", unsafe_allow_html=True)
        else:
            h = st.columns([3, 1, 1, 2, 1, 1])
            for hc, ht in zip(h, ["File", "Type", "Rows", "Uploaded", "", ""]):
                hc.markdown(
                    f"<p style='font-size:0.72rem;font-weight:600;color:#6b7280;"
                    f"text-transform:uppercase;letter-spacing:0.05em;margin:0;'>{ht}</p>",
                    unsafe_allow_html=True,
                )
            st.markdown("<hr style='margin:6px 0;border-color:#1f1f1f;'>", unsafe_allow_html=True)

            for f in biz_files:
                is_active  = f["file_id"] == st.session_state.active_file_id
                name_color = "#a5b4fc" if is_active else "#e5e5e5"
                rc = st.columns([3, 1, 1, 2, 1, 1])
                rc[0].markdown(
                    f"<p style='font-size:0.85rem;color:{name_color};margin:0;"
                    f"font-weight:{'600' if is_active else '400'};'>"
                    f"{'  ' if is_active else ''}{f['file_name']}</p>",
                    unsafe_allow_html=True,
                )
                rc[1].markdown(
                    f"<p style='font-size:0.83rem;color:#9ca3af;margin:0;'>{f['file_type'].upper()}</p>",
                    unsafe_allow_html=True,
                )
                rc[2].markdown(
                    f"<p style='font-size:0.83rem;color:#9ca3af;margin:0;'>{f['row_count']:,}</p>",
                    unsafe_allow_html=True,
                )
                rc[3].markdown(
                    f"<p style='font-size:0.83rem;color:#6b7280;margin:0;'>"
                    f"{f['uploaded_at'][:16].replace('T', ' ')}</p>",
                    unsafe_allow_html=True,
                )
                btn_label = "Active" if is_active else "Load"
                if rc[4].button(btn_label, key=f"load_{f['file_id']}", disabled=is_active):
                    if not get_cached_file(f["file_id"]):
                        restored = restore_file_from_disk(f["file_id"])
                        if not restored:
                            st.warning("File not in memory - please re-upload.")
                    cached = get_cached_file(f["file_id"])
                    if cached:
                        _set_active(f["file_id"], f["file_name"], f["file_type"], cached["processed"])
                        st.success(f"Loaded '{f['file_name']}' - switch to Chat tab!")
                        st.rerun()
                if rc[5].button("  ", key=f"del_data_{f['file_id']}"):
                    delete_business_file(f["file_id"])
                    if st.session_state.active_file_id == f["file_id"]:
                        for k in ["active_file_id", "active_file_name", "active_file_type", "active_processed"]:
                            st.session_state[k] = None
                    st.rerun()
                st.markdown("<hr style='margin:4px 0;border-color:#1a1a1a;'>", unsafe_allow_html=True)

    # -- CHAT ------------------------------------------------------------------
    with tab_chat:
        st.markdown("<p class='sec-title'>Chat with Your Data</p>", unsafe_allow_html=True)

        if not _data_active_banner():
            st.stop()

        _, ctrl_right = st.columns([4, 1])
        with ctrl_right:
            if st.button("Clear memory", use_container_width=True):
                reset_business_memory(st.session_state.active_file_id)
                st.session_state.data_chat_history = []
                st.rerun()

        st.markdown("<p class='muted' style='margin-bottom:6px;'>Try asking</p>", unsafe_allow_html=True)
        chip_cols = st.columns(4)
        for idx, ex in enumerate(BIZ_EXAMPLES):
            with chip_cols[idx % 4]:
                if st.button(ex, key=f"data_chip_{idx}", use_container_width=True):
                    st.session_state.data_pending_query = ex
                    st.rerun()

        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        data_history = st.session_state.data_chat_history
        if not data_history:
            st.markdown(f"""
            <div class="empty-box">
                <div class="empty-icon"> </div>
                <div class="empty-title">Ask anything about {st.session_state.active_file_name}</div>
                <div class="empty-sub">Charts auto-generate for visual questions</div>
            </div>""", unsafe_allow_html=True)
        else:
            for turn in data_history:
                if len(turn) == 3:
                    q, a, follow_ups = turn
                    chart_result = None
                else:
                    q, a, follow_ups, chart_result = turn

                with st.chat_message("user", avatar=" "):
                    st.markdown(q)
                with st.chat_message("assistant", avatar=" "):
                    st.markdown(a)
                    if chart_result and chart_result.get("fig"):
                        st.plotly_chart(
                            chart_result["fig"],
                            use_container_width=True,
                            key=f"chart_{chart_result.get('chart_id', hash(q))}",
                        )
                    if follow_ups:
                        st.markdown(
                            "<p class='muted' style='margin-top:8px;'>Follow-up suggestions:</p>",
                            unsafe_allow_html=True,
                        )
                        fu_cols = st.columns(3)
                        for i, fu in enumerate(follow_ups[:3]):
                            with fu_cols[i % 3]:
                                if st.button(fu, key=f"fu_{hash(fu)}_{i}", use_container_width=True):
                                    st.session_state.data_pending_query = fu
                                    st.rerun()

        with st.form("data_chat_form", clear_on_submit=True):
            col_in, col_btn = st.columns([10, 1])
            with col_in:
                user_query = st.text_input(
                    "q", value=st.session_state.data_pending_query,
                    placeholder="Ask anything about your data...",
                    label_visibility="collapsed",
                )
            with col_btn:
                submitted = st.form_submit_button("Send", use_container_width=True)

        query_to_run = user_query.strip() or st.session_state.data_pending_query.strip()

        if submitted and query_to_run:
            st.session_state.data_pending_query = ""
            if not _check_rate_limit():
                st.warning("Rate limit reached. Wait a moment.")
            else:
                with st.spinner("Analyzing..."):
                    try:
                        result = answer_question(
                            file_id=st.session_state.active_file_id,
                            query=query_to_run,
                        )
                        st.session_state.data_chat_history.append((
                            query_to_run,
                            result["answer"],
                            result["follow_ups"],
                            result.get("chart"),
                        ))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Something went wrong: {e}")

    # -- VISUALIZE -------------------------------------------------------------
    with tab_viz:
        st.markdown("<p class='sec-title'>Visualize</p>", unsafe_allow_html=True)

        if not _data_active_banner():
            st.stop()

        cached = get_cached_file(st.session_state.active_file_id)
        if not cached:
            st.warning("File not in memory - please re-upload.")
            st.stop()

        file_data  = cached["file_data"]
        sheet_name = file_data.sheet_names[0]
        df         = file_data.dataframes[sheet_name]
        all_cols   = list(df.columns)
        num_cols   = df.select_dtypes(include=["number"]).columns.tolist()
        processed  = st.session_state.active_processed

        st.markdown(
            "<p class='sec-title' style='font-size:0.95rem;'> Chart Builder</p>",
            unsafe_allow_html=True,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            chart_type = st.selectbox(
                "Chart Type",
                ["bar", "line", "pie", "hist", "scatter"],
                format_func=lambda x: {
                    "bar":     " Bar - compare categories",
                    "line":    "  Line - show trends",
                    "pie":     "  Pie - show distribution",
                    "hist":    "  Histogram - numeric distribution",
                    "scatter": "  Scatter - two numeric columns",
                }[x],
            )
        with c2:
            x_col = st.selectbox("X Axis / Labels", all_cols)
        with c3:
            y_col = st.selectbox(
                "Y Axis / Values", ["None"] + num_cols
            ) if chart_type != "hist" else None

        chart_title = st.text_input("Chart Title (optional)", placeholder="Leave blank for auto title")

        if st.button("Generate Chart", type="primary", key="manual_chart"):
            with st.spinner("Generating..."):
                result = generate_chart(
                    df=df,
                    chart_type=chart_type,
                    x_col=x_col,
                    y_col=y_col if y_col and y_col != "None" else None,
                    file_id=st.session_state.active_file_id,
                    file_name=st.session_state.active_file_name,
                    title=chart_title,
                )
                if result.get("error"):
                    st.error(f"Chart failed: {result['error']}")
                else:
                    st.plotly_chart(result["fig"], use_container_width=True)

        st.markdown("---")
        st.markdown(
            "<p class='sec-title' style='font-size:0.95rem;'>  AI Insights</p>",
            unsafe_allow_html=True,
        )
        db_file  = get_business_file(st.session_state.active_file_id)
        insights = db_file.get("summary", "") if db_file else ""
        if insights:
            st.markdown(insights)
        else:
            st.markdown("<p class='muted'>No insights yet - re-upload to generate.</p>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            "<p class='sec-title' style='font-size:0.95rem;'>  Anomalies</p>",
            unsafe_allow_html=True,
        )
        anomalies = processed.get("anomalies", []) if processed else []
        if not anomalies:
            st.markdown(
                "<p class='muted' style='color:#4ade80;'>  No anomalies detected.</p>",
                unsafe_allow_html=True,
            )
        else:
            for a in anomalies:
                st.markdown(
                    f"<div class='src-card'>"
                    f"{_severity_emoji(a['severity'])} "
                    f"<b>{a['type'].replace('_', ' ').title()}</b>"
                    f" - <code>{a['column']}</code><br>"
                    f"<span style='color:#9ca3af;font-size:0.82rem;'>{a['detail']}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            if st.button("Explain Anomalies with AI", type="primary"):
                with st.spinner("Analyzing..."):
                    try:
                        explanation = get_anomaly_explanation(st.session_state.active_file_id)
                        st.session_state.anomaly_explanation = explanation
                    except Exception as e:
                        st.error(f"Failed: {e}")
            if st.session_state.anomaly_explanation:
                st.markdown("---")
                st.markdown(st.session_state.anomaly_explanation)

    # -- REPORT ----------------------------------------------------------------
    with tab_report:
        st.markdown("<p class='sec-title'>Report</p>", unsafe_allow_html=True)

        if not _data_active_banner():
            st.stop()

        st.markdown(
            "<p class='sec-title' style='font-size:0.95rem;'>  Executive Summary</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='muted'>A professional summary a senior manager can read in under 2 minutes.</p>",
            unsafe_allow_html=True,
        )

        if st.button("Generate Executive Summary", type="primary"):
            with st.spinner("Generating..."):
                try:
                    summary = get_executive_summary(st.session_state.active_file_id)
                    st.session_state.exec_summary = summary
                except Exception as e:
                    st.error(f"Failed: {e}")

        if st.session_state.exec_summary:
            st.markdown("---")
            st.markdown(st.session_state.exec_summary)

        st.markdown("---")
        st.markdown(
            "<p class='sec-title' style='font-size:0.95rem;'>  Download Full Report</p>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p class='muted'>Full markdown report - statistics, anomalies, insights, executive summary.</p>",
            unsafe_allow_html=True,
        )

        if st.button("Build & Download Report", type="primary"):
            with st.spinner("Building report..."):
                try:
                    processed    = st.session_state.active_processed
                    exec_summary = (
                        st.session_state.exec_summary
                        or get_executive_summary(st.session_state.active_file_id)
                    )
                    db_file  = get_business_file(st.session_state.active_file_id)
                    insights = db_file.get("summary", "") if db_file else ""

                    result = generate_report(
                        file_name=st.session_state.active_file_name,
                        summary=processed["summary"],
                        anomalies=processed["anomalies"],
                        insights=insights,
                        exec_summary=exec_summary,
                    )

                    with open(result["file_path"], "r", encoding="utf-8") as f:
                        report_content = f.read()

                    st.success("Report ready!")
                    st.download_button(
                        label="  Download Report (.md)",
                        data=report_content,
                        file_name=f"report_{st.session_state.active_file_name}.md",
                        mime="text/markdown",
                    )
                    st.markdown("---")
                    st.markdown(
                        "<p class='sec-title' style='font-size:0.9rem;'>Preview</p>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        report_content[:3000]
                        + ("\n\n*... [full report in download]*" if len(report_content) > 3000 else "")
                    )
                except Exception as e:
                    st.error(f"Report generation failed: {e}")