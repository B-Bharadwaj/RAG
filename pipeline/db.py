"""
pipeline/db.py

SQLite-backed registry.

New tables
----------
question_history
    id          INTEGER PRIMARY KEY AUTOINCREMENT
    query       TEXT
    answer      TEXT
    scope       TEXT    (filename or "All PDFs")
    asked_at    TEXT    (ISO-8601)

New column on documents
-----------------------
    pdf_summary TEXT    — auto-generated 3-paragraph summary of the paper
"""

import sqlite3
import uuid
import json
from datetime import datetime, timezone
from config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        # ── Documents table ────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id        TEXT PRIMARY KEY,
                filename      TEXT NOT NULL,
                page_count    INTEGER DEFAULT 0,
                chunk_count   INTEGER DEFAULT 0,
                uploaded_at   TEXT NOT NULL,
                pdf_metadata  TEXT DEFAULT '{}',
                pdf_summary   TEXT DEFAULT ''
            )
        """)
        # Migrations — safe on existing DBs
        for col, default in [
            ("pdf_metadata", "'{}'"),
            ("pdf_summary",  "''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE documents ADD COLUMN {col} TEXT DEFAULT {default}")
            except sqlite3.OperationalError:
                pass

        # ── Question history table ─────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS question_history (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                query     TEXT NOT NULL,
                answer    TEXT NOT NULL,
                scope     TEXT NOT NULL DEFAULT 'All PDFs',
                asked_at  TEXT NOT NULL
            )
        """)

        # ── Feedback table ─────────────────────────────────────────────────
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                query      TEXT NOT NULL,
                answer     TEXT NOT NULL,
                rating     TEXT NOT NULL,   -- 'up' or 'down'
                scope      TEXT NOT NULL DEFAULT 'All PDFs',
                rated_at   TEXT NOT NULL
            )
        """)
        conn.commit()


# ---------------------------------------------------------------------------
# Document registry
# ---------------------------------------------------------------------------

def generate_doc_id() -> str:
    return str(uuid.uuid4())


def register_document(doc_id: str, filename: str, page_count: int, chunk_count: int):
    uploaded_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents (doc_id, filename, page_count, chunk_count, uploaded_at, pdf_metadata, pdf_summary)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, filename, page_count, chunk_count, uploaded_at, "{}", ""),
        )
        conn.commit()


def update_document_metadata(doc_id: str, metadata: dict):
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET pdf_metadata = ? WHERE doc_id = ?",
            (json.dumps(metadata), doc_id),
        )
        conn.commit()


def update_document_summary(doc_id: str, summary: str):
    """Store the auto-generated paper summary."""
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET pdf_summary = ? WHERE doc_id = ?",
            (summary, doc_id),
        )
        conn.commit()


def get_document_summary(doc_id: str) -> str:
    """Return the stored summary, or empty string if not yet generated."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT pdf_summary FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    return row["pdf_summary"] if row and row["pdf_summary"] else ""


def get_all_documents() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents ORDER BY uploaded_at DESC"
        ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        for key in ("pdf_metadata",):
            try:
                d[key] = json.loads(d.get(key) or "{}")
            except (json.JSONDecodeError, TypeError):
                d[key] = {}
        results.append(d)
    return results


def get_document(doc_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE doc_id = ?", (doc_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    try:
        d["pdf_metadata"] = json.loads(d.get("pdf_metadata") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["pdf_metadata"] = {}
    return d


def delete_document(doc_id: str):
    with _connect() as conn:
        conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        conn.commit()


def filename_exists(filename: str) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM documents WHERE filename = ?", (filename,)
        ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Question history
# ---------------------------------------------------------------------------

def save_question(query: str, answer: str, scope: str):
    """Save a question/answer pair to history."""
    asked_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO question_history (query, answer, scope, asked_at) VALUES (?, ?, ?, ?)",
            (query, answer, scope, asked_at),
        )
        conn.commit()


def get_question_history(limit: int = 20) -> list[dict]:
    """Return the most recent questions, newest first."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM question_history ORDER BY asked_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_question_history():
    """Wipe all question history."""
    with _connect() as conn:
        conn.execute("DELETE FROM question_history")
        conn.commit()


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback(query: str, answer: str, rating: str, scope: str):
    """Save a thumbs up/down rating for a query/answer pair."""
    rated_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO feedback (query, answer, rating, scope, rated_at) VALUES (?, ?, ?, ?, ?)",
            (query, answer, rating, scope, rated_at),
        )
        conn.commit()


def get_feedback_summary() -> dict:
    """Return count of thumbs up and thumbs down ratings."""
    with _connect() as conn:
        up   = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating='up'").fetchone()[0]
        down = conn.execute("SELECT COUNT(*) FROM feedback WHERE rating='down'").fetchone()[0]
    return {"up": up, "down": down}

# ---------------------------------------------------------------------------
# Eval scores  (Project 5 addition — paste at bottom of db.py)
# ---------------------------------------------------------------------------

def _ensure_eval_table():
    """Create eval_scores table if it doesn't exist. Called lazily."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eval_scores (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                query           TEXT NOT NULL,
                answer          TEXT NOT NULL,
                chunks          TEXT NOT NULL DEFAULT '[]',
                faithfulness    REAL,
                relevancy       REAL,
                context_recall  REAL,
                reasoning       TEXT,
                scope           TEXT NOT NULL DEFAULT 'All PDFs',
                scored_at       TEXT NOT NULL
            )
        """)
        conn.commit()

_ensure_eval_table()


def save_eval_score(
    query: str,
    answer: str,
    chunks: list[str],
    faithfulness: float,
    relevancy: float,
    context_recall: float,
    reasoning: str,
    scope: str = "All PDFs",
):
    """Persist one judge evaluation result."""
    import json as _json
    scored_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO eval_scores
              (query, answer, chunks, faithfulness, relevancy, context_recall, reasoning, scope, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query, answer,
                _json.dumps(chunks),
                faithfulness, relevancy, context_recall,
                reasoning, scope, scored_at,
            ),
        )
        conn.commit()


def get_eval_scores(limit: int = 200) -> list[dict]:
    """Return eval results newest-first."""
    import json as _json
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_scores ORDER BY scored_at DESC LIMIT ?", (limit,)
        ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["chunks"] = _json.loads(d.get("chunks") or "[]")
        except Exception:
            d["chunks"] = []
        results.append(d)
    return results


def get_recent_queries(limit: int = 20) -> list[dict]:
    """
    Return the most recent question_history rows that have NOT yet been
    eval-scored (used by the manual trigger button).
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT qh.* FROM question_history qh
            WHERE qh.query NOT IN (
                SELECT query FROM eval_scores
            )
            ORDER BY qh.asked_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_eval_summary() -> dict:
    """Aggregate averages across all scored rows."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*)               AS total,
                AVG(faithfulness)      AS avg_faithfulness,
                AVG(relevancy)         AS avg_relevancy,
                AVG(context_recall)    AS avg_context_recall
            FROM eval_scores
            """
        ).fetchone()
    if not row or row["total"] == 0:
        return {"total": 0, "avg_faithfulness": 0.0,
                "avg_relevancy": 0.0, "avg_context_recall": 0.0}
    return {
        "total":               row["total"],
        "avg_faithfulness":    round(row["avg_faithfulness"] or 0.0, 3),
        "avg_relevancy":       round(row["avg_relevancy"]    or 0.0, 3),
        "avg_context_recall":  round(row["avg_context_recall"] or 0.0, 3),
    }


def clear_eval_scores():
    with _connect() as conn:
        conn.execute("DELETE FROM eval_scores")
        conn.commit()
        
init_db()

# ===========================================================================
# v2 ADDITIONS — Business Intelligence tables
# ===========================================================================

def _ensure_business_tables():
    """Create v2-specific tables for business file registry and analysis history."""
    with _connect() as conn:

        # ── Business file registry ─────────────────────────────────────────
        # Tracks uploaded Excel/CSV files separately from PDF documents
        conn.execute("""
            CREATE TABLE IF NOT EXISTS business_files (
                file_id       TEXT PRIMARY KEY,
                file_name     TEXT NOT NULL,
                file_type     TEXT NOT NULL,        -- 'excel' or 'csv'
                sheet_names   TEXT NOT NULL,        -- JSON array of sheet names
                row_count     INTEGER DEFAULT 0,
                col_count     INTEGER DEFAULT 0,
                uploaded_at   TEXT NOT NULL,
                summary       TEXT DEFAULT ''       -- auto generated summary
            )
        """)

        # ── Analysis history ───────────────────────────────────────────────
        # Tracks every Q&A interaction on business files
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_history (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id       TEXT NOT NULL,
                file_name     TEXT NOT NULL,
                query         TEXT NOT NULL,
                answer        TEXT NOT NULL,
                sheet_name    TEXT DEFAULT '',
                asked_at      TEXT NOT NULL
            )
        """)

        # ── Chart registry ─────────────────────────────────────────────────
        # Tracks generated charts so UI can display them
        conn.execute("""
            CREATE TABLE IF NOT EXISTS charts (
                chart_id      TEXT PRIMARY KEY,
                file_id       TEXT NOT NULL,
                chart_type    TEXT NOT NULL,        -- 'bar', 'line', 'pie'
                title         TEXT NOT NULL,
                file_path     TEXT NOT NULL,        -- path to saved HTML chart
                created_at    TEXT NOT NULL
            )
        """)

        conn.commit()

_ensure_business_tables()


# ── Business file registry CRUD ────────────────────────────────────────────

def register_business_file(
    file_id: str,
    file_name: str,
    file_type: str,
    sheet_names: list[str],
    row_count: int,
    col_count: int,
) -> None:
    """Register an uploaded Excel or CSV file."""
    import json as _json
    uploaded_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO business_files
              (file_id, file_name, file_type, sheet_names, row_count, col_count, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id, file_name, file_type,
                _json.dumps(sheet_names),
                row_count, col_count, uploaded_at,
            ),
        )
        conn.commit()


def get_all_business_files() -> list[dict]:
    """Return all registered business files newest first."""
    import json as _json
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM business_files ORDER BY uploaded_at DESC"
        ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["sheet_names"] = _json.loads(d.get("sheet_names") or "[]")
        except Exception:
            d["sheet_names"] = []
        results.append(d)
    return results


def get_business_file(file_id: str) -> dict | None:
    """Return a single business file by ID."""
    import json as _json
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM business_files WHERE file_id = ?", (file_id,)
        ).fetchone()
    if row is None:
        return None
    d = dict(row)
    try:
        d["sheet_names"] = _json.loads(d.get("sheet_names") or "[]")
    except Exception:
        d["sheet_names"] = []
    return d


def delete_business_file(file_id: str) -> None:
    """Delete a business file and its analysis history."""
    with _connect() as conn:
        conn.execute("DELETE FROM business_files WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM analysis_history WHERE file_id = ?", (file_id,))
        conn.execute("DELETE FROM charts WHERE file_id = ?", (file_id,))
        conn.commit()


def update_business_file_summary(file_id: str, summary: str) -> None:
    """Store the auto generated summary for a business file."""
    with _connect() as conn:
        conn.execute(
            "UPDATE business_files SET summary = ? WHERE file_id = ?",
            (summary, file_id),
        )
        conn.commit()


def business_file_exists(file_name: str) -> bool:
    """Check if a file with this name is already registered."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM business_files WHERE file_name = ?", (file_name,)
        ).fetchone()
    return row is not None


# ── Analysis history CRUD ──────────────────────────────────────────────────

def save_analysis(
    file_id: str,
    file_name: str,
    query: str,
    answer: str,
    sheet_name: str = "",
) -> None:
    """Save a Q&A interaction on a business file."""
    asked_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_history
              (file_id, file_name, query, answer, sheet_name, asked_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_id, file_name, query, answer, sheet_name, asked_at),
        )
        conn.commit()


def get_analysis_history(file_id: str, limit: int = 50) -> list[dict]:
    """Return analysis history for a specific file newest first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM analysis_history
            WHERE file_id = ?
            ORDER BY asked_at DESC
            LIMIT ?
            """,
            (file_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_all_analysis_history(limit: int = 100) -> list[dict]:
    """Return all analysis history across all files."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM analysis_history ORDER BY asked_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


# ── Chart registry CRUD ────────────────────────────────────────────────────

def save_chart(
    chart_id: str,
    file_id: str,
    chart_type: str,
    title: str,
    file_path: str,
) -> None:
    """Register a generated chart."""
    created_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO charts
              (chart_id, file_id, chart_type, title, file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chart_id, file_id, chart_type, title, file_path, created_at),
        )
        conn.commit()


def get_charts_for_file(file_id: str) -> list[dict]:
    """Return all charts generated for a specific file."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM charts WHERE file_id = ? ORDER BY created_at DESC",
            (file_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def generate_file_id() -> str:
    """Generate a unique file ID."""
    return str(uuid.uuid4())
