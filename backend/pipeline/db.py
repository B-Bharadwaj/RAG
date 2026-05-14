"""
pipeline/db.py

SQLite-backed registry — PDF Mode only.

Tables:
    documents         — indexed PDF registry
    question_history  — PDF chat history
    feedback          — thumbs up/down ratings
    eval_scores       — judge LLM evaluation scores

NOTE: All Data Mode tables (business_files, analysis_history,
query_log) have moved to PostgreSQL in services/sql_engine.py
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
                conn.execute(
                    f"ALTER TABLE documents ADD COLUMN {col} TEXT DEFAULT {default}"
                )
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
                rating     TEXT NOT NULL,
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


def register_document(
    doc_id: str,
    filename: str,
    page_count: int,
    chunk_count: int,
):
    uploaded_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO documents
              (doc_id, filename, page_count, chunk_count,
               uploaded_at, pdf_metadata, pdf_summary)
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
    with _connect() as conn:
        conn.execute(
            "UPDATE documents SET pdf_summary = ? WHERE doc_id = ?",
            (summary, doc_id),
        )
        conn.commit()


def get_document_summary(doc_id: str) -> str:
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
        try:
            d["pdf_metadata"] = json.loads(d.get("pdf_metadata") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["pdf_metadata"] = {}
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
    asked_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO question_history (query, answer, scope, asked_at)
            VALUES (?, ?, ?, ?)
            """,
            (query, answer, scope, asked_at),
        )
        conn.commit()


def get_question_history(limit: int = 20) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM question_history ORDER BY asked_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def clear_question_history():
    with _connect() as conn:
        conn.execute("DELETE FROM question_history")
        conn.commit()


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

def save_feedback(query: str, answer: str, rating: str, scope: str):
    rated_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO feedback (query, answer, rating, scope, rated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (query, answer, rating, scope, rated_at),
        )
        conn.commit()


def get_feedback_summary() -> dict:
    with _connect() as conn:
        up   = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating='up'"
        ).fetchone()[0]
        down = conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE rating='down'"
        ).fetchone()[0]
    return {"up": up, "down": down}


# ---------------------------------------------------------------------------
# Eval scores
# ---------------------------------------------------------------------------

def _ensure_eval_table():
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
    query:          str,
    answer:         str,
    chunks:         list[str],
    faithfulness:   float,
    relevancy:      float,
    context_recall: float,
    reasoning:      str,
    scope:          str = "All PDFs",
):
    scored_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO eval_scores
              (query, answer, chunks, faithfulness, relevancy,
               context_recall, reasoning, scope, scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query, answer,
                json.dumps(chunks),
                faithfulness, relevancy, context_recall,
                reasoning, scope, scored_at,
            ),
        )
        conn.commit()


def get_eval_scores(limit: int = 200) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_scores ORDER BY scored_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["chunks"] = json.loads(d.get("chunks") or "[]")
        except Exception:
            d["chunks"] = []
        results.append(d)
    return results


def get_recent_queries(limit: int = 20) -> list[dict]:
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
        return {
            "total":              0,
            "avg_faithfulness":   0.0,
            "avg_relevancy":      0.0,
            "avg_context_recall": 0.0,
        }
    return {
        "total":              row["total"],
        "avg_faithfulness":   round(row["avg_faithfulness"]   or 0.0, 3),
        "avg_relevancy":      round(row["avg_relevancy"]      or 0.0, 3),
        "avg_context_recall": round(row["avg_context_recall"] or 0.0, 3),
    }


def clear_eval_scores():
    with _connect() as conn:
        conn.execute("DELETE FROM eval_scores")
        conn.commit()


init_db()
