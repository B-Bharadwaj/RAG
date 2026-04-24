"""
routers/analyzer.py

All FastAPI endpoints for the Business Intelligence analyzer.

Endpoints:
    POST /upload          — upload and process a business file
    POST /question        — ask a question about a file
    GET  /summary/{file_id}   — get executive summary
    GET  /anomalies/{file_id} — get anomaly explanation
    POST /chart           — generate a chart
    GET  /files           — list all uploaded files
    GET  /files/{file_id} — get info about a specific file
    DELETE /files/{file_id}   — delete a file
    GET  /history/{file_id}   — get analysis history
    GET  /health          — health check
"""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional

from services.analyzer import (
    process_uploaded_file,
    answer_question,
    get_executive_summary,
    get_anomaly_explanation,
    get_cached_file,
)
from services.chart_generator import generate_chart, get_suggested_charts
from services.report_generator import generate_report
from pipeline.db import (
    get_all_business_files,
    get_business_file,
    delete_business_file,
    get_analysis_history,
)
from models.schemas import (
    QuestionRequest,
    QuestionResponse,
    SummaryRequest,
    SummaryResponse,
    ChartRequest,
    ChartResponse,
    AnomalyResponse,
    AnomalyDetail,
    FileInfoResponse,
    UploadResponse,
    ReportResponse,
    HealthResponse,
)

router = APIRouter()


# ── Health Check ───────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Basic health check — confirms the API is running."""
    return HealthResponse(status="ok", version="2.0")


# ── File Upload ────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file:       UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
):
    """
    Upload and process a business file (Excel, CSV, or PDF).

    - Saves file to disk
    - Runs Pandas analysis
    - Generates AI insights
    - Registers in SQLite
    """
    # Validate file type
    allowed = {".csv", ".xlsx", ".xls", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code = 400,
            detail      = f"Unsupported file type '{ext}'. Allowed: {allowed}",
        )

    # Read file bytes
    file_bytes = await file.read()

    # Validate file size
    max_bytes = 50 * 1024 * 1024   # 50 MB
    if len(file_bytes) > max_bytes:
        raise HTTPException(
            status_code = 400,
            detail      = f"File too large. Max size is 50MB.",
        )

    # Process
    try:
        result = process_uploaded_file(
            file_bytes = file_bytes,
            file_name  = file.filename,
            sheet_name = sheet_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return UploadResponse(
        file_id      = result["file_id"],
        file_name    = result["file_name"],
        file_type    = result["file_type"],
        status       = result["status"],
        sheet_names  = result["sheet_names"],
        shape        = result["shape"],
        insights     = result["insights"],
        anomaly_count= len(result["anomalies"]),
    )


# ── Question Answering ─────────────────────────────────────────────────────

@router.post("/question", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Ask a natural language question about an uploaded file.
    Maintains conversation memory per file.
    """
    result = answer_question(
        file_id    = request.file_id,
        query      = request.query,
        sheet_name = request.sheet_name,
    )

    if "File not found" in result["answer"]:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    return QuestionResponse(
        file_id    = request.file_id,
        query      = request.query,
        answer     = result["answer"],
        follow_ups = result["follow_ups"],
    )


# ── Executive Summary ──────────────────────────────────────────────────────

@router.get("/summary/{file_id}", response_model=SummaryResponse)
async def get_summary(file_id: str):
    """Generate an executive summary for an uploaded file."""
    summary = get_executive_summary(file_id)

    if "File not found" in summary:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    return SummaryResponse(file_id=file_id, summary=summary)


# ── Anomaly Explanation ────────────────────────────────────────────────────

@router.get("/anomalies/{file_id}", response_model=AnomalyResponse)
async def get_anomalies(file_id: str):
    """Get detected anomalies with AI explanation."""
    cached = get_cached_file(file_id)
    if not cached:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    anomalies    = cached["processed"]["anomalies"]
    explanation  = get_anomaly_explanation(file_id)

    return AnomalyResponse(
        file_id     = file_id,
        anomalies   = [AnomalyDetail(**a) for a in anomalies],
        explanation = explanation,
    )


# ── Chart Generation ───────────────────────────────────────────────────────

@router.post("/chart", response_model=ChartResponse)
async def create_chart(request: ChartRequest):
    """Generate a Plotly chart for an uploaded file."""
    cached = get_cached_file(request.file_id)
    if not cached:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    # Get the right DataFrame
    file_data  = cached["file_data"]
    sheet_name = request.sheet_name or file_data.sheet_names[0]

    if sheet_name not in file_data.dataframes:
        raise HTTPException(status_code=400, detail=f"Sheet '{sheet_name}' not found.")

    df = file_data.dataframes[sheet_name]

    # Validate columns exist
    if request.x_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{request.x_col}' not found.")
    if request.y_col and request.y_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{request.y_col}' not found.")

    result = generate_chart(
        df         = df,
        chart_type = request.chart_type,
        x_col      = request.x_col,
        y_col      = request.y_col,
        file_id    = request.file_id,
        file_name  = file_data.file_name,
        title      = request.title or "",
        color_col  = request.color_col,
    )

    if "error" in result and result["error"]:
        raise HTTPException(status_code=500, detail=result["error"])

    return ChartResponse(
        chart_id  = result["chart_id"],
        file_id   = request.file_id,
        title     = result["title"],
        file_path = result["file_path"],
    )


# ── Report Generation ──────────────────────────────────────────────────────

@router.get("/report/{file_id}", response_model=ReportResponse)
async def generate_file_report(file_id: str):
    """Generate a downloadable markdown report for a file."""
    cached = get_cached_file(file_id)
    if not cached:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    processed  = cached["processed"]
    file_name  = cached["file_data"].file_name

    # Generate executive summary first
    exec_summary = get_executive_summary(file_id)

    # Get insights from DB
    from pipeline.db import get_business_file as _get_bf
    db_file  = _get_bf(file_id)
    insights = db_file.get("summary", "") if db_file else ""

    result = generate_report(
        file_name    = file_name,
        summary      = processed["summary"],
        anomalies    = processed["anomalies"],
        insights     = insights,
        exec_summary = exec_summary,
    )

    return ReportResponse(
        report_id = result["report_id"],
        file_id   = file_id,
        file_path = result["file_path"],
        timestamp = result["timestamp"],
    )


# ── Download Report ────────────────────────────────────────────────────────

@router.get("/download/report/{report_id}")
async def download_report(report_id: str):
    """Download a generated report as a markdown file."""
    from config import REPORTS_DIR
    file_path = os.path.join(REPORTS_DIR, f"{report_id}_report.md")

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report not found.")

    return FileResponse(
        path             = file_path,
        filename         = f"report_{report_id}.md",
        media_type       = "text/markdown",
    )


# ── File Management ────────────────────────────────────────────────────────

@router.get("/files", response_model=list[FileInfoResponse])
async def list_files():
    """List all uploaded business files."""
    files = get_all_business_files()
    return [
        FileInfoResponse(
            file_id     = f["file_id"],
            file_name   = f["file_name"],
            file_type   = f["file_type"],
            sheet_names = f["sheet_names"],
            row_count   = f["row_count"],
            col_count   = f["col_count"],
            uploaded_at = f["uploaded_at"],
            summary     = f["summary"],
        )
        for f in files
    ]


@router.get("/files/{file_id}", response_model=FileInfoResponse)
async def get_file_info(file_id: str):
    """Get info about a specific uploaded file."""
    f = get_business_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")

    return FileInfoResponse(
        file_id     = f["file_id"],
        file_name   = f["file_name"],
        file_type   = f["file_type"],
        sheet_names = f["sheet_names"],
        row_count   = f["row_count"],
        col_count   = f["col_count"],
        uploaded_at = f["uploaded_at"],
        summary     = f["summary"],
    )


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """Delete a file and all its associated data."""
    f = get_business_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")

    # Delete from DB
    delete_business_file(file_id)

    # Remove from memory cache
    from services.analyzer import _file_cache
    _file_cache.pop(file_id, None)

    # Delete uploaded file from disk
    from config import UPLOADS_DIR
    for fname in os.listdir(UPLOADS_DIR):
        if fname.startswith(file_id):
            try:
                os.remove(os.path.join(UPLOADS_DIR, fname))
            except Exception:
                pass

    return {"status": "deleted", "file_id": file_id}


# ── Analysis History ───────────────────────────────────────────────────────

@router.get("/history/{file_id}")
async def get_history(file_id: str, limit: int = 20):
    """Get Q&A history for a specific file."""
    history = get_analysis_history(file_id, limit=limit)
    return {"file_id": file_id, "history": history}
