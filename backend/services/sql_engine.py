"""
services/sql_engine.py

PostgreSQL connection, CSV/Excel loading, schema extraction,
and SQL execution for the Text-to-SQL pipeline.
"""

import pandas as pd
import psycopg2
import psycopg2.extras
from sqlalchemy import create_engine, text
from config import (
    POSTGRES_HOST, POSTGRES_PORT,
    POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD,
)


# ── Connection ─────────────────────────────────────────────────────────────

def get_connection():
    """Get a raw psycopg2 connection."""
    return psycopg2.connect(
        host     = POSTGRES_HOST,
        port     = int(POSTGRES_PORT),
        dbname   = POSTGRES_DB,
        user     = POSTGRES_USER,
        password = POSTGRES_PASSWORD,
    )


def get_engine():
    """Get a SQLAlchemy engine for pandas operations."""
    return create_engine(
        f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )


def test_connection() -> bool:
    """Returns True if PostgreSQL is reachable."""
    try:
        conn = get_connection()
        conn.close()
        return True
    except Exception as e:
        print(f"[PostgreSQL] Connection failed: {e}")
        return False


# ── Load Data ──────────────────────────────────────────────────────────────

def sanitize_table_name(file_id: str, sheet_name: str) -> str:
    """
    Build a safe PostgreSQL table name.
    Format: f_{first 8 chars of file_id}_{sheet_name}
    All non-alphanumeric chars replaced with underscore.
    """
    raw = f"f_{file_id[:8]}_{sheet_name}"
    return "".join(
        c if c.isalnum() or c == "_" else "_"
        for c in raw.lower()
    )


def load_dataframe_to_postgres(
    df: pd.DataFrame,
    file_id: str,
    sheet_name: str,
) -> str:
    """
    Load a single DataFrame into a PostgreSQL table.
    Replaces the table if it already exists.
    Returns the table name created.
    """
    table_name = sanitize_table_name(file_id, sheet_name)
    engine     = get_engine()

    df.to_sql(
        table_name,
        engine,
        if_exists = "replace",
        index     = False,
    )

    print(f"[PostgreSQL] Loaded {len(df):,} rows → table '{table_name}'")
    return table_name


def load_file_to_postgres(file_data, file_id: str) -> dict[str, str]:
    """
    Load all sheets from a FileData object into PostgreSQL.

    Returns:
        dict mapping sheet name → postgres table name
        e.g. {"Sheet1": "f_abc12345_sheet1"}
    """
    table_map = {}

    for sheet_name, df in file_data.dataframes.items():
        table_name             = load_dataframe_to_postgres(df, file_id, sheet_name)
        table_map[sheet_name]  = table_name

    return table_map


# ── Schema Extraction ──────────────────────────────────────────────────────

def get_schema(table_names: list[str]) -> str:
    """
    Extract schema from PostgreSQL for the given tables.
    Returns a formatted string sent to the LLM as context.

    Format per table:
        Table: table_name
        Columns: col1 (type), col2 (type), ...
        Sample rows: [(val1, val2), ...]
    """
    conn   = get_connection()
    cursor = conn.cursor()
    schema = ""

    try:
        for table in table_names:
            # Get column names and types
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                  AND table_schema = 'public'
                ORDER BY ordinal_position
            """, (table,))
            cols = cursor.fetchall()

            if not cols:
                continue

            col_defs = ", ".join(f"{c[0]} ({c[1]})" for c in cols)
            schema  += f"Table: {table}\n"
            schema  += f"Columns: {col_defs}\n"

            # Get 3 sample rows
            cursor.execute(f'SELECT * FROM "{table}" LIMIT 3')
            rows    = cursor.fetchall()
            schema += f"Sample rows: {rows}\n\n"

    finally:
        cursor.close()
        conn.close()

    return schema.strip()


# ── SQL Execution ──────────────────────────────────────────────────────────

def execute_sql(sql: str) -> dict:
    """
    Execute a SQL query on PostgreSQL.

    Returns:
    {
        "success":   bool,
        "columns":   list of column names,
        "rows":      list of tuples (max 50),
        "row_count": int,
        "error":     str or None,
    }
    """
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute(sql)
        raw_rows = cursor.fetchall()

        if not raw_rows:
            return {
                "success":   True,
                "columns":   [],
                "rows":      [],
                "row_count": 0,
                "error":     None,
            }

        columns  = list(raw_rows[0].keys())
        rows     = [tuple(r.values()) for r in raw_rows]

        return {
            "success":   True,
            "columns":   columns,
            "rows":      rows[:50],
            "row_count": len(rows),
            "error":     None,
        }

    except Exception as e:
        conn.rollback()
        return {
            "success":   False,
            "columns":   [],
            "rows":      [],
            "row_count": 0,
            "error":     str(e),
        }

    finally:
        cursor.close()
        conn.close()


# ── Cleanup ────────────────────────────────────────────────────────────────

def drop_file_tables(table_names: list[str]) -> None:
    """
    Drop all PostgreSQL tables for a file.
    Called when a file is deleted from the system.
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        for table in table_names:
            cursor.execute(f'DROP TABLE IF EXISTS "{table}"')
            print(f"[PostgreSQL] Dropped table '{table}'")
        conn.commit()

    finally:
        cursor.close()
        conn.close()

# =============================================================================
# Data Mode — PostgreSQL Table Management
# =============================================================================

import json
from datetime import datetime, timezone


def create_tables() -> None:
    """
    Create all Data Mode tables in PostgreSQL if they don't exist.
    Called once on startup from main.py.

    Tables created:
        business_files    — uploaded CSV/Excel file registry
        analysis_history  — every Q&A for data mode
        query_log         — every SQL query generated by LLM
    """
    conn   = get_connection()
    cursor = conn.cursor()

    try:
        # ── business_files ─────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS business_files (
                file_id     TEXT PRIMARY KEY,
                file_name   TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                sheet_names TEXT NOT NULL,
                row_count   INTEGER DEFAULT 0,
                col_count   INTEGER DEFAULT 0,
                uploaded_at TEXT NOT NULL,
                summary     TEXT DEFAULT ''
            )
        """)

        # ── analysis_history ───────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id          SERIAL PRIMARY KEY,
                file_id     TEXT NOT NULL,
                file_name   TEXT NOT NULL,
                query       TEXT NOT NULL,
                answer      TEXT NOT NULL,
                sheet_name  TEXT DEFAULT '',
                asked_at    TEXT NOT NULL
            )
        """)

        # ── query_log ──────────────────────────────────────────────────────
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS query_log (
                id          SERIAL PRIMARY KEY,
                log_id      TEXT NOT NULL,
                file_id     TEXT NOT NULL,
                file_name   TEXT NOT NULL,
                question    TEXT NOT NULL,
                sql         TEXT NOT NULL,
                status      TEXT NOT NULL,
                result_rows INTEGER DEFAULT 0,
                error       TEXT DEFAULT '',
                asked_at    TEXT NOT NULL
            )
        """)

        conn.commit()
        print("[PostgreSQL] All Data Mode tables created/verified.")

    finally:
        cursor.close()
        conn.close()


# =============================================================================
# Business File Registry
# =============================================================================

def register_business_file(
    file_id:     str,
    file_name:   str,
    file_type:   str,
    sheet_names: list,
    row_count:   int,
    col_count:   int,
) -> None:
    """Register an uploaded business file in PostgreSQL."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO business_files
              (file_id, file_name, file_type, sheet_names,
               row_count, col_count, uploaded_at, summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (file_id) DO UPDATE SET
              file_name   = EXCLUDED.file_name,
              file_type   = EXCLUDED.file_type,
              sheet_names = EXCLUDED.sheet_names,
              row_count   = EXCLUDED.row_count,
              col_count   = EXCLUDED.col_count,
              uploaded_at = EXCLUDED.uploaded_at
        """, (
            file_id,
            file_name,
            file_type,
            json.dumps(sheet_names),
            row_count,
            col_count,
            datetime.now(timezone.utc).isoformat(),
            "",
        ))
        conn.commit()
        print(f"[PostgreSQL] Registered file: {file_name}")
    finally:
        cursor.close()
        conn.close()


def get_business_file(file_id: str) -> dict | None:
    """Get a single business file by file_id."""
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute(
            "SELECT * FROM business_files WHERE file_id = %s",
            (file_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        result = dict(row)
        result["sheet_names"] = json.loads(result["sheet_names"])
        return result
    finally:
        cursor.close()
        conn.close()


def get_all_business_files() -> list[dict]:
    """Get all uploaded business files newest first."""
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("""
            SELECT * FROM business_files
            ORDER BY uploaded_at DESC
        """)
        rows = cursor.fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["sheet_names"] = json.loads(r["sheet_names"])
            result.append(r)
        return result
    finally:
        cursor.close()
        conn.close()


def delete_business_file(file_id: str) -> None:
    """Delete a business file registry entry from PostgreSQL."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "DELETE FROM business_files WHERE file_id = %s",
            (file_id,)
        )
        conn.commit()
        print(f"[PostgreSQL] Deleted file registry: {file_id}")
    finally:
        cursor.close()
        conn.close()


def update_business_file_summary(file_id: str, summary: str) -> None:
    """Update the AI summary for a business file."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE business_files SET summary = %s WHERE file_id = %s",
            (summary, file_id)
        )
        conn.commit()
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# Analysis History
# =============================================================================

def save_analysis(
    file_id:    str,
    file_name:  str,
    query:      str,
    answer:     str,
    sheet_name: str = "",
) -> None:
    """Save a Q&A entry to analysis history."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO analysis_history
              (file_id, file_name, query, answer, sheet_name, asked_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            file_id,
            file_name,
            query,
            answer,
            sheet_name,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
    finally:
        cursor.close()
        conn.close()


def get_analysis_history(
    file_id: str,
    limit:   int = 20,
) -> list[dict]:
    """Get Q&A history for a file newest first."""
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("""
            SELECT * FROM analysis_history
            WHERE file_id = %s
            ORDER BY asked_at DESC
            LIMIT %s
        """, (file_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


# =============================================================================
# Query Log
# =============================================================================

def save_query_log_pg(
    file_id:     str,
    file_name:   str,
    question:    str,
    sql:         str,
    status:      str,
    result_rows: int = 0,
    error:       str = "",
) -> str:
    """Save a generated SQL query to PostgreSQL query_log."""
    import uuid
    log_id   = str(uuid.uuid4())[:8]
    asked_at = datetime.now(timezone.utc).isoformat()

    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO query_log
              (log_id, file_id, file_name, question,
               sql, status, result_rows, error, asked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            log_id, file_id, file_name, question,
            sql, status, result_rows, error, asked_at,
        ))
        conn.commit()
        print(f"[PostgreSQL] Query log saved — status={status}")
        return log_id
    finally:
        cursor.close()
        conn.close()


def get_query_logs_pg(
    file_id: str = None,
    limit:   int = 100,
) -> list[dict]:
    """Get query logs from PostgreSQL newest first."""
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if file_id:
            cursor.execute("""
                SELECT * FROM query_log
                WHERE file_id = %s
                ORDER BY asked_at DESC
                LIMIT %s
            """, (file_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM query_log
                ORDER BY asked_at DESC
                LIMIT %s
            """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()


def get_query_log_summary_pg() -> dict:
    """Get summary stats from PostgreSQL query_log."""
    conn   = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cursor.execute("""
            SELECT
                COUNT(*)                                           AS total,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
                SUM(CASE WHEN status = 'error'   THEN 1 ELSE 0 END) AS errors,
                SUM(CASE WHEN status = 'not_sql' THEN 1 ELSE 0 END) AS not_sql
            FROM query_log
        """)
        row = dict(cursor.fetchone())
        return {
            "total":   row["total"]   or 0,
            "success": row["success"] or 0,
            "errors":  row["errors"]  or 0,
            "not_sql": row["not_sql"] or 0,
        }
    finally:
        cursor.close()
        conn.close()


def clear_query_logs_pg(file_id: str = None) -> None:
    """Clear query logs from PostgreSQL."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        if file_id:
            cursor.execute(
                "DELETE FROM query_log WHERE file_id = %s",
                (file_id,)
            )
        else:
            cursor.execute("DELETE FROM query_log")
        conn.commit()
        print(f"[PostgreSQL] Query logs cleared — file_id={file_id or 'ALL'}")
    finally:
        cursor.close()
        conn.close()    

def business_file_exists(file_name: str) -> bool:
    """Check if a file with this name is already registered."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM business_files WHERE file_name = %s",
            (file_name,)
        )
        return cursor.fetchone() is not None
    finally:
        cursor.close()
        conn.close()

def save_chart(
    chart_id:   str,
    file_id:    str,
    chart_type: str,
    title:      str,
    file_path:  str,
) -> None:
    """Save a generated chart record to PostgreSQL."""
    conn   = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS charts (
                chart_id   TEXT PRIMARY KEY,
                file_id    TEXT NOT NULL,
                chart_type TEXT NOT NULL,
                title      TEXT NOT NULL,
                file_path  TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            INSERT INTO charts (chart_id, file_id, chart_type, title, file_path, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (chart_id) DO NOTHING
        """, (
            chart_id, file_id, chart_type, title, file_path,
            datetime.now(timezone.utc).isoformat(),
        ))
        conn.commit()
    finally:
        cursor.close()
        conn.close()