"""
services/analyzer.py

Orchestrates the full analysis pipeline for an uploaded business file.
Ties together: loader -> PostgreSQL -> generator -> db

v3 changes:
    - Summary generation uses SQL queries instead of stats compression
    - Anomaly detection uses SQL queries instead of IQR method
    - All Data Mode DB operations use PostgreSQL via sql_engine
    - File cache stored in Streamlit session state
"""

import os
import uuid
import streamlit as st

from pipeline.loader    import load_file, FileData
from pipeline.processor import process_file
from services.sql_engine import (
    register_business_file,
    get_business_file,
    get_all_business_files,
    delete_business_file,
    update_business_file_summary,
    save_analysis,
    get_analysis_history,
    sanitize_table_name,
    business_file_exists,
    load_file_to_postgres,
    test_connection,
    get_schema,
    execute_sql,
)
from generation.generator import (
    ask_business_question_with_chart,
    explain_anomalies,
    generate_summary_queries,
    generate_sql_summary,
    generate_anomaly_queries,
    generate_sql_anomaly_explanation,
    generate_executive_summary,
)
from config import UPLOADS_DIR

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


# -- Cache helpers ----------------------------------------------------------

# Module-level cache - persists for the lifetime of the FastAPI process
_file_cache: dict = {}

def _get_cache() -> dict:
    return _file_cache

def get_cached_file(file_id: str) -> dict | None:
    """Return cached file data - auto restores from disk if not in memory."""
    cached = _file_cache.get(file_id)
    if cached:
        return cached

    # Not in memory - try to restore from disk automatically
    log.info("File %s not in cache - attempting restore from disk", file_id)
    restored = restore_file_from_disk(file_id)
    if restored:
        return _file_cache.get(file_id)

    return None

def get_all_cached_files() -> list[str]:
    """Return all file_ids currently in memory."""
    return list(_file_cache.keys())


# -- File Upload & Processing -----------------------------------------------

def process_uploaded_file(
    file_bytes: bytes,
    file_name:  str,
    sheet_name: str = None,
) -> dict:
    """
    Full pipeline for an uploaded business file.

    Steps:
        1. Save file to disk
        2. Load with Pandas (file I/O only)
        3. Load into PostgreSQL
        4. Generate SQL-driven insights
        5. Register in PostgreSQL business_files
        6. Store in session cache
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
    file_id   = str(uuid.uuid4())
    save_path = os.path.join(UPLOADS_DIR, f"{file_id}_{file_name}")

    with open(save_path, "wb") as f:
        f.write(file_bytes)

    # Load file using Pandas (file I/O only)
    file_data = load_file(save_path, file_name)

    # Process file - keep for fallback context + shape info
    processed = process_file(file_data, sheet_name)

    # -- Load into PostgreSQL -----------------------------------------------
    table_map = {}
    try:
        if test_connection():
            table_map = load_file_to_postgres(file_data, file_id)
            log.info("PostgreSQL tables created: %s", table_map)
        else:
            log.warning("PostgreSQL not reachable - skipping SQL load")
    except Exception as e:
        log.error("PostgreSQL load failed: %s", e)

    # Store in session cache
    _get_cache()[file_id] = {
        "file_data": file_data,
        "processed": processed,
        "save_path": save_path,
        "table_map": table_map,
    }

    # -- Generate SQL-driven insights ---------------------------------------
    insights = ""
    try:
        table_names = list(table_map.values())
        if table_names:
            schema  = get_schema(table_names)
            queries = generate_summary_queries(schema)

            results_text = ""
            for i, sql in enumerate(queries, 1):
                try:
                    result = execute_sql(sql)
                    if result["success"] and result["rows"]:
                        results_text += (
                            f"Query {i}: {sql}\n"
                            f"Result: {result['rows'][:5]}\n\n"
                        )
                except Exception as qe:
                    log.warning("Summary query %d failed: %s", i, qe)

            if results_text:
                insights = generate_sql_summary(
                    file_name = file_name,
                    schema    = schema,
                    results   = results_text,
                )
    except Exception as e:
        log.error("SQL-driven insights failed: %s", e)

    # -- Register in PostgreSQL ---------------------------------------------
    if not business_file_exists(file_name):
        register_business_file(
            file_id     = file_id,
            file_name   = file_name,
            file_type   = file_data.file_type,
            sheet_names = file_data.sheet_names,
            row_count   = file_data.row_count,
            col_count   = file_data.col_count,
        )

    # Save insights as summary
    if insights:
        update_business_file_summary(file_id, insights)

    return {
        "file_id":     file_id,
        "file_name":   file_name,
        "status":      "success",
        "file_type":   file_data.file_type,
        "sheet_names": file_data.sheet_names,
        "shape":       processed.get("shape", [0, 0]),
        "context":     processed.get("context", ""),
        "summary":     processed.get("summary", {}),
        "anomalies":   processed.get("anomalies", []),
        "insights":    insights,
    }


# -- Restore from disk on server restart -----------------------------------

def restore_file_from_disk(file_id: str) -> bool:
    """
    Restore a file from disk into the in-memory cache.
    Rebuilds the PostgreSQL table_map from existing tables.
    """
    db_file = get_business_file(file_id)
    if not db_file:
        return False

    save_path = None
    for fname in os.listdir(UPLOADS_DIR):
        if fname.startswith(file_id):
            save_path = os.path.join(UPLOADS_DIR, fname)
            break

    if not save_path or not os.path.exists(save_path):
        return False

    try:
        file_data = load_file(save_path, db_file["file_name"])
        processed = process_file(file_data)

        # Rebuild table_map - tables already exist in PostgreSQL
        table_map = {}
        try:
            if test_connection():
                for sheet in file_data.sheet_names:
                    table_name        = sanitize_table_name(file_id, sheet)
                    table_map[sheet]  = table_name
                log.info("Restored table_map: %s", table_map)
        except Exception as e:
            log.warning("Could not restore table_map: %s", e)

        _get_cache()[file_id] = {
            "file_data": file_data,
            "processed": processed,
            "save_path": save_path,
            "table_map": table_map,
        }

        log.info("Restored file from disk: %s", db_file["file_name"])
        return True

    except Exception as e:
        log.error("Restore failed: %s", e)
        return False


# -- Q&A --------------------------------------------------------------------

def answer_question(
    file_id:    str,
    query:      str,
    sheet_name: str = None,
) -> dict:
    """
    Answer a question using Text-to-SQL on PostgreSQL.
    Falls back to stats-based answer if SQL fails or returns NOT_SQL.
    """
    from services.query_logger import save_query_log
    from generation.generator  import (
        generate_sql_query,
        sql_result_to_answer,
        ask_business_question_with_chart,
    )

    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        if not restore_file_from_disk(file_id):
            return {
                "answer":     "File not found. Please re-upload.",
                "follow_ups": [],
                "chart":      None,
                "sql":        None,
            }
        cached = _get_cache().get(file_id)

    file_name = cached["file_data"].file_name
    table_map = cached.get("table_map", {})
    sheet     = sheet_name or cached["file_data"].sheet_names[0]
    df        = cached["file_data"].dataframes.get(sheet)
    context   = cached["processed"].get("context", "")

    # -- Try Text-to-SQL ----------------------------------------------------
    if table_map:
        try:
            table_names = list(table_map.values())
            schema      = get_schema(table_names)
            sql         = generate_sql_query(query, schema)

            if sql and sql.strip().upper() != "NOT_SQL":
                result = execute_sql(sql)

                save_query_log(
                    file_id     = file_id,
                    file_name   = file_name,
                    question    = query,
                    sql         = sql,
                    status      = "success" if result["success"] else "error",
                    result_rows = result["row_count"],
                    error       = result.get("error") or "",
                )

                if result["success"] and result["rows"]:
                    answer = sql_result_to_answer(
                        question = query,
                        columns  = result["columns"],
                        rows     = result["rows"],
                    )

                    # Generate chart if visual question
                    chart_result = None
                    try:
                        from services.chart_generator import (
                            needs_chart, generate_chat_chart,
                        )
                        if needs_chart(query) and df is not None:
                            chart_result = generate_chat_chart(
                                query     = query,
                                df        = df,
                                file_id   = file_id,
                                file_name = file_name,
                            )
                    except Exception as ce:
                        log.warning("Chart generation failed: %s", ce)

                    # Follow-up suggestions
                    follow_ups = []
                    try:
                        from generation.generator import _business_followup_suggestions
                        follow_ups = _business_followup_suggestions(query, answer)
                    except Exception:
                        pass

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
                        "sql":        sql,
                    }

            else:
                save_query_log(
                    file_id   = file_id,
                    file_name = file_name,
                    question  = query,
                    sql       = sql or "NOT_SQL",
                    status    = "not_sql",
                )

        except Exception as e:
            log.error("Text-to-SQL pipeline failed: %s", e)

    # -- Fallback - stats based ---------------------------------------------
    log.info("Falling back to stats-based answer for: %s", query)
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
        "sql":        None,
    }


# -- Executive Summary ------------------------------------------------------

def get_executive_summary(file_id: str) -> str:
    """
    Generate an executive summary using SQL queries on PostgreSQL.
    Falls back to stats-based summary if SQL fails.
    """
    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        if not restore_file_from_disk(file_id):
            return "File not found. Please re-upload."
        cached = _get_cache().get(file_id)

    file_name = cached["file_data"].file_name
    table_map = cached.get("table_map", {})

    # Try SQL-driven executive summary
    if table_map:
        try:
            table_names  = list(table_map.values())
            schema       = get_schema(table_names)
            queries      = generate_summary_queries(schema)
            results_text = ""

            for i, sql in enumerate(queries, 1):
                try:
                    result = execute_sql(sql)
                    if result["success"] and result["rows"]:
                        results_text += (
                            f"Query {i}: {sql}\n"
                            f"Result: {result['rows'][:5]}\n\n"
                        )
                except Exception as qe:
                    log.warning("Summary query %d failed: %s", i, qe)

            if results_text:
                return generate_sql_summary(
                    file_name = file_name,
                    schema    = schema,
                    results   = results_text,
                )
        except Exception as e:
            log.error("SQL executive summary failed: %s", e)

    # Fallback
    return generate_executive_summary(
        context   = cached["processed"].get("context", ""),
        file_name = file_name,
    )


# -- Anomaly Explanation ----------------------------------------------------

def get_anomaly_explanation(file_id: str) -> str:
    """
    Detect and explain anomalies using SQL queries on PostgreSQL.
    Falls back to stats-based explanation if SQL fails.
    """
    cache  = _get_cache()
    cached = cache.get(file_id)

    if not cached:
        if not restore_file_from_disk(file_id):
            return "File not found. Please re-upload."
        cached = _get_cache().get(file_id)

    file_name = cached["file_data"].file_name
    table_map = cached.get("table_map", {})

    # Try SQL-driven anomaly detection
    if table_map:
        try:
            table_names  = list(table_map.values())
            schema       = get_schema(table_names)
            queries      = generate_anomaly_queries(schema)
            results_text = ""

            for i, sql in enumerate(queries, 1):
                try:
                    result = execute_sql(sql)
                    if result["success"]:
                        results_text += (
                            f"Check {i}: {sql}\n"
                            f"Result: {result['rows'][:5]}\n\n"
                        )
                except Exception as qe:
                    log.warning("Anomaly query %d failed: %s", i, qe)

            if results_text:
                return generate_sql_anomaly_explanation(
                    file_name = file_name,
                    results   = results_text,
                )
        except Exception as e:
            log.error("SQL anomaly detection failed: %s", e)

    # Fallback
    return explain_anomalies(
        context   = cached["processed"].get("context", ""),
        anomalies = cached["processed"].get("anomalies", []),
    )