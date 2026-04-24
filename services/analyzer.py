"""
services/analyzer.py

Orchestrates the full analysis pipeline for a uploaded business file.
Ties together: loader → processor → generator → db

v2 fix: file cache is stored in Streamlit session state instead of
a module-level dict, so it survives Streamlit reruns.
"""

import os
import streamlit as st
from pipeline.loader import load_file, FileData
from pipeline.processor import process_file
from pipeline.db import (
    register_business_file,
    update_business_file_summary,
    save_analysis,
    business_file_exists,
    generate_file_id,
    get_business_file,
)
from generation.generator import (
    ask_business_question_with_chart,
    generate_business_insights,
    generate_executive_summary,
    explain_anomalies,
)
from config import UPLOADS_DIR


# ── Cache helpers ──────────────────────────────────────────────────────────
# We store the file cache in st.session_state so it survives reruns.

def _get_cache() -> dict:
    """Return the file cache from session state."""
    if "_file_cache" not in st.session_state:
        st.session_state["_file_cache"] = {}
    return st.session_state["_file_cache"]


def get_cached_file(file_id: str) -> dict | None:
    """Return cached file data for a file_id."""
    return _get_cache().get(file_id)


def get_all_cached_files() -> list[str]:
    """Return all file_ids currently in memory."""
    return list(_get_cache().keys())


# ── File Upload & Processing ───────────────────────────────────────────────

def process_uploaded_file(
    file_bytes: bytes,
    file_name: str,
    sheet_name: str = None,
) -> dict:
    """
    Full pipeline for an uploaded file.
    Cache is stored in session state so it survives reruns.
    """
    cache = _get_cache()

    # Check if already in session cache
    for fid, cached in cache.items():
        if cached["file_data"].file_name == file_name:
            return {
                "file_id":    fid,
                "file_name":  file_name,
                "status":     "already_exists",
                "file_type":  cached["file_data"].file_type,
                "sheet_names":cached["file_data"].sheet_names,
                **cached["processed"],
            }

    # Save file to disk
    file_id   = generate_file_id()
    save_path = os.path.join(UPLOADS_DIR, f"{file_id}_{file_name}")

    with open(save_path, "wb") as f:
        f.write(file_bytes)

    # Load file
    file_data = load_file(save_path, file_name)

    # Process file
    processed = process_file(file_data, sheet_name)

    # Register in DB
    if not business_file_exists(file_name):
        register_business_file(
            file_id     = file_id,
            file_name   = file_name,
            file_type   = file_data.file_type,
            sheet_names = file_data.sheet_names,
            row_count   = file_data.row_count,
            col_count   = file_data.col_count,
        )

    # Store in session state cache
    cache[file_id] = {
        "file_data": file_data,
        "processed": processed,
        "save_path": save_path,
    }
    st.session_state["_file_cache"] = cache

    # Generate insights
    insights = generate_business_insights(
        context   = processed["context"],
        file_name = file_name,
    )

    # Save insights as summary
    update_business_file_summary(file_id, insights)

    return {
        "file_id":     file_id,
        "file_name":   file_name,
        "status":      "success",
        "file_type":   file_data.file_type,
        "sheet_names": file_data.sheet_names,
        "shape":       processed["shape"],
        "context":     processed["context"],
        "summary":     processed["summary"],
        "anomalies":   processed["anomalies"],
        "insights":    insights,
    }


# ── Restore from disk on app restart ──────────────────────────────────────

def restore_file_from_disk(file_id: str) -> bool:
    """
    If a file_id exists in DB but not in session cache,
    reload it from the saved file on disk.

    Called automatically when user tries to load a previous file.
    """
    cache = _get_cache()
    if file_id in cache:
        return True   # already in memory

    db_file = get_business_file(file_id)
    if not db_file:
        return False

    # Find the file on disk
    file_name = db_file["file_name"]
    save_path = os.path.join(UPLOADS_DIR, f"{file_id}_{file_name}")

    if not os.path.exists(save_path):
        return False   # file deleted from disk

    try:
        file_data = load_file(save_path, file_name)
        processed = process_file(file_data)

        cache[file_id] = {
            "file_data": file_data,
            "processed": processed,
            "save_path": save_path,
        }
        st.session_state["_file_cache"] = cache
        return True

    except Exception as e:
        print(f"[restore] Failed to restore {file_name}: {e}")
        return False


# ── Q&A ────────────────────────────────────────────────────────────────────

def answer_question(
    file_id: str,
    query: str,
    sheet_name: str = None,
) -> dict:
    """Answer a question about an uploaded business file."""
    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        # Try restoring from disk
        if restore_file_from_disk(file_id):
            cached = _get_cache().get(file_id)
        else:
            return {
                "answer":     "File not found. Please re-upload.",
                "follow_ups": [],
                "chart":      None,
            }

    # Re-process if sheet changed
    current_sheet = cached["processed"].get("sheet_name")
    if sheet_name and sheet_name != current_sheet:
        cached["processed"] = process_file(cached["file_data"], sheet_name)
        cache[file_id] = cached
        st.session_state["_file_cache"] = cache

    context   = cached["processed"]["context"]
    file_name = cached["file_data"].file_name
    sheet     = sheet_name or current_sheet or cached["file_data"].sheet_names[0]
    df        = cached["file_data"].dataframes.get(sheet)

    answer, follow_ups, chart_result = ask_business_question_with_chart(
        query     = query,
        context   = context,
        file_id   = file_id,
        file_name = file_name,
        df        = df,
    )

    save_analysis(
        file_id    = file_id,
        file_name  = file_name,
        query      = query,
        answer     = answer,
        sheet_name = sheet,
    )

    return {
        "answer":     answer,
        "follow_ups": follow_ups,
        "chart":      chart_result,
    }


# ── Executive Summary ──────────────────────────────────────────────────────

def get_executive_summary(file_id: str) -> str:
    """Generate an executive summary for an uploaded file."""
    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        if restore_file_from_disk(file_id):
            cached = _get_cache().get(file_id)
        else:
            return "File not found. Please re-upload."

    return generate_executive_summary(
        context   = cached["processed"]["context"],
        file_name = cached["file_data"].file_name,
    )


# ── Anomaly Explanation ────────────────────────────────────────────────────

def get_anomaly_explanation(file_id: str) -> str:
    """Explain detected anomalies in plain business language."""
    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        if restore_file_from_disk(file_id):
            cached = _get_cache().get(file_id)
        else:
            return "File not found. Please re-upload."

    return explain_anomalies(
        context   = cached["processed"]["context"],
        anomalies = cached["processed"]["anomalies"],
    )
