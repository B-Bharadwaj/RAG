"""
routers/sql.py

API endpoints for the SQL query log.
Allows the frontend and your mentor to inspect
every SQL query the LLM has generated.

All endpoints prefixed with /api/v2 (registered in main.py)
"""

from fastapi import APIRouter
from services.query_logger import (
    get_query_logs,
    get_query_log_summary,
    clear_query_logs,
)

router = APIRouter()


# -- Get all query logs -----------------------------------------------------

@router.get("/query-log")
async def list_query_logs(limit: int = 100):
    """
    Get all SQL query logs across all files.
    Returns newest first.
    """
    logs = get_query_logs(limit=limit)
    return {
        "total": len(logs),
        "logs":  logs,
    }


# -- Get logs for a specific file -------------------------------------------

@router.get("/query-log/{file_id}")
async def get_file_query_logs(file_id: str, limit: int = 100):
    """
    Get SQL query logs for a specific file.
    Returns newest first.
    """
    logs = get_query_logs(file_id=file_id, limit=limit)
    return {
        "file_id": file_id,
        "total":   len(logs),
        "logs":    logs,
    }


# -- Summary stats ----------------------------------------------------------

@router.get("/query-log-summary")
async def query_log_summary():
    """
    Get summary statistics across all logged queries.

    Returns:
        total   -> total queries logged
        success -> queries that ran successfully
        errors  -> queries that threw an error
        not_sql -> questions LLM couldn't answer with SQL
    """
    return get_query_log_summary()


# -- Clear logs -------------------------------------------------------------

@router.delete("/query-log")
async def clear_all_query_logs():
    """Clear all SQL query logs."""
    clear_query_logs()
    return {"status": "cleared", "message": "All query logs deleted."}


@router.delete("/query-log/{file_id}")
async def clear_file_query_logs(file_id: str):
    """Clear SQL query logs for a specific file."""
    clear_query_logs(file_id=file_id)
    return {
        "status":  "cleared",
        "file_id": file_id,
        "message": f"Query logs cleared for file {file_id}.",
    }