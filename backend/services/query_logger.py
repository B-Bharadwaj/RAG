"""
services/query_logger.py

Query log functions — now backed by PostgreSQL.
All data stored in the query_log table in PostgreSQL.

This file is kept as a clean interface so the rest of
the codebase doesn't need to import directly from sql_engine.
"""

from services.sql_engine import (
    save_query_log_pg      as save_query_log,
    get_query_logs_pg      as get_query_logs,
    get_query_log_summary_pg as get_query_log_summary,
    clear_query_logs_pg    as clear_query_logs,
)

__all__ = [
    "save_query_log",
    "get_query_logs",
    "get_query_log_summary",
    "clear_query_logs",
]