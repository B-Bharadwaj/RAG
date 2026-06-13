"""
routers/analyzer.py

All FastAPI endpoints for the Business Intelligence analyzer.
"""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Depends
from fastapi.responses import FileResponse
from typing import Optional

from services.analyzer import (
    process_uploaded_file,
    answer_question,
    get_executive_summary,
    get_anomaly_explanation,
    get_cached_file,
    restore_file_from_disk,
)
from middleware.auth_middleware import get_current_user
from services.chart_generator import generate_chart, get_suggested_charts
from services.report_generator import generate_report
from services.sql_engine import (
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

def _extract_datasets(fig, chart_type: str) -> list:
    COLORS = [
        "#6366f1", "#ec4899", "#14b8a6",
        "#f59e0b", "#8b5cf6", "#10b981",
        "#ef4444", "#3b82f6",
    ]
    datasets = []
    for i, trace in enumerate(fig.data):
        color = COLORS[i % len(COLORS)]
        if chart_type == "pie":
            ds = {
                "label":           getattr(trace, "name", "") or f"Series {i+1}",
                "data":            [float(v) for v in trace.values] if hasattr(trace, "values") and trace.values is not None else [],
                "backgroundColor": COLORS[:len(trace.values)] if hasattr(trace, "values") and trace.values is not None else [],
                "borderWidth":     1,
            }
        else:
            ds = {
                "label":           str(getattr(trace, "name", "") or f"Series {i+1}"),
                "data":            [float(v) for v in trace.y] if hasattr(trace, "y") and trace.y is not None else [],
                "backgroundColor": color,
                "borderColor":     color,
                "borderWidth":     2,
                "borderRadius":    4,
            }
            if chart_type == "line":
                ds["fill"]    = False
                ds["tension"] = 0.3
        datasets.append(ds)
    return datasets


# -- Health Check -----------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", version="2.0")


# -- Columns ----------------------------------------------------------------

@router.get("/columns/{file_id}")
async def get_column_values(
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    cached = get_cached_file(file_id)
    if not cached:
        if not restore_file_from_disk(file_id):
            raise HTTPException(status_code=404, detail="File not found. Please re-upload.")
        cached = get_cached_file(file_id)

    file_data  = cached["file_data"]
    sheet_name = file_data.sheet_names[0]
    df         = file_data.dataframes[sheet_name]

    columns = []
    for col in df.columns:
        dtype        = str(df[col].dtype)
        unique_count = int(df[col].nunique())
        is_numeric   = "int" in dtype or "float" in dtype

        if is_numeric:
            columns.append({
                "name":          col,
                "type":          "numeric",
                "unique_count":  unique_count,
                "min":           float(df[col].min()),
                "max":           float(df[col].max()),
                "unique_values": [],
            })
        elif unique_count <= 50:
            unique_vals = sorted([str(v) for v in df[col].dropna().unique().tolist()])
            columns.append({
                "name":          col,
                "type":          "categorical",
                "unique_count":  unique_count,
                "unique_values": unique_vals,
                "min":           None,
                "max":           None,
            })
        else:
            columns.append({
                "name":          col,
                "type":          "high_cardinality",
                "unique_count":  unique_count,
                "unique_values": [],
                "min":           None,
                "max":           None,
            })

    return {
        "file_id":     file_id,
        "file_name":   file_data.file_name,
        "sheet_names": file_data.sheet_names,
        "columns":     columns,
    }


# -- File Upload ------------------------------------------------------------

@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file:         UploadFile = File(...),
    sheet_name:   Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    allowed = {".csv", ".xlsx", ".xls", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'.")

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max size is 50MB.")

    try:
        result = process_uploaded_file(
            file_bytes = file_bytes,
            file_name  = file.filename,
            sheet_name = sheet_name,
            user_id    = current_user["user_id"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return UploadResponse(
        file_id       = result["file_id"],
        file_name     = result["file_name"],
        file_type     = result["file_type"],
        status        = result["status"],
        sheet_names   = result.get("sheet_names", []),
        shape         = result.get("shape", [0, 0]),
        insights      = result.get("insights", ""),
        anomaly_count = len(result.get("anomalies", [])),
    )


# -- Question Answering -----------------------------------------------------

@router.post("/question", response_model=QuestionResponse)
async def ask_question(
    request:      QuestionRequest,
    current_user: dict = Depends(get_current_user),
):
    result = answer_question(
        file_id    = request.file_id,
        query      = request.query,
        sheet_name = request.sheet_name,
        user_id    = current_user["user_id"],
    )

    if "File not found" in result["answer"]:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    chart_data = None
    chart = result.get("chart")
    if chart and chart.get("fig"):
        try:
            fig   = chart["fig"]
            trace = fig.data[0] if fig.data else None
            ct    = chart.get("chart_type")
            if ct == "pie":
                lbl = [str(v) for v in trace.labels] if trace and hasattr(trace, "labels") and trace.labels is not None else []
                val = [float(v) for v in trace.values] if trace and hasattr(trace, "values") and trace.values is not None else []
            else:
                lbl = [str(v) for v in trace.x] if trace and hasattr(trace, "x") and trace.x is not None else []
                val = [float(v) for v in trace.y] if trace and hasattr(trace, "y") and trace.y is not None else []
            chart_data = {
                "chart_id":   chart.get("chart_id"),
                "title":      chart.get("title"),
                "chart_type": ct,
                "labels":     lbl,
                "values":     val,
                "datasets":   _extract_datasets(fig, ct),
            }
        except Exception:
            chart_data = None
    
    if chart_data:
        try:
            import json as _json
            from services.sql_engine import update_analysis_chart_data, get_analysis_history
            history = get_analysis_history(request.file_id, limit=1, offset=0, user_id=current_user["user_id"])
            if history:
                update_analysis_chart_data(history[0]["id"], _json.dumps(chart_data))
        except Exception:
            pass

    return QuestionResponse(
        file_id    = request.file_id,
        query      = request.query,
        answer     = result["answer"],
        follow_ups = result.get("follow_ups", []),
        sql        = result.get("sql"),
        chart      = chart_data,
    )


# -- Executive Summary ------------------------------------------------------

@router.get("/summary/{file_id}", response_model=SummaryResponse)
async def get_summary(
    file_id:      str,
    current_user: dict = Depends(get_current_user),
):
    summary = get_executive_summary(file_id)
    if "File not found" in summary:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")
    return SummaryResponse(file_id=file_id, summary=summary)


# -- Anomaly Explanation ----------------------------------------------------

@router.get("/anomalies/{file_id}", response_model=AnomalyResponse)
async def get_anomalies(
    file_id:      str,
    current_user: dict = Depends(get_current_user),
):
    cached = get_cached_file(file_id)
    if not cached:
        if not restore_file_from_disk(file_id):
            raise HTTPException(status_code=404, detail="File not found. Please re-upload.")
        cached = get_cached_file(file_id)

    anomalies   = cached["processed"].get("anomalies", [])
    explanation = get_anomaly_explanation(file_id)
    return AnomalyResponse(
        file_id     = file_id,
        anomalies   = [AnomalyDetail(**a) for a in anomalies],
        explanation = explanation,
    )


# -- Chart Generation -------------------------------------------------------

@router.post("/chart", response_model=ChartResponse)
async def create_chart(
    request:      ChartRequest,
    current_user: dict = Depends(get_current_user),
):
    cached = get_cached_file(request.file_id)
    if not cached:
        if not restore_file_from_disk(request.file_id):
            raise HTTPException(status_code=404, detail="File not found. Please re-upload.")
        cached = get_cached_file(request.file_id)

    file_data  = cached["file_data"]
    sheet_name = request.sheet_name or file_data.sheet_names[0]
    table_map  = cached.get("table_map", {})

    if table_map:
        from generation.generator import generate_manual_chart_sql
        from services.sql_engine  import execute_sql

        table_name = table_map.get(sheet_name) or list(table_map.values())[0]
        sql = generate_manual_chart_sql(
            table_name    = table_name,
            x_col         = request.x_col,
            y_col         = request.y_col,
            aggregation   = request.aggregation,
            filter_col    = request.filter_col or request.x_col,
            filter_values = request.filter_values,
            chart_type    = request.chart_type,
        )
        print(f"[DEBUG] Generated SQL: {repr(sql)}")
        result = execute_sql(sql)

        if not result["success"] or not result["rows"]:
            raise HTTPException(status_code=400, detail=f"SQL returned no results. Error: {result.get('error')}")

        import pandas as pd
        chart_df = pd.DataFrame(result["rows"], columns=result["columns"])
    else:
        if sheet_name not in file_data.dataframes:
            raise HTTPException(status_code=400, detail=f"Sheet '{sheet_name}' not found.")
        chart_df = file_data.dataframes[sheet_name]

    if request.chart_type != "hist" and request.x_col not in chart_df.columns:
        raise HTTPException(status_code=400, detail=f"Column '{request.x_col}' not found in result.")

    from services.chart_generator import generate_chart
    x_col_actual = chart_df.columns[0] if not chart_df.empty else request.x_col
    y_col_actual = None
    if request.chart_type != "hist":
        y_col_actual = request.y_col if request.y_col and request.y_col in chart_df.columns else (chart_df.columns[1] if len(chart_df.columns) > 1 else None)

    result = generate_chart(
        df         = chart_df,
        chart_type = request.chart_type,
        x_col      = x_col_actual,
        y_col      = y_col_actual,
        file_id    = request.file_id,
        file_name  = file_data.file_name,
        title      = request.title or "",
        color_col  = request.color_col,
    )

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    labels   = []
    values   = []
    datasets = []

    if result.get("fig"):
        try:
            fig   = result["fig"]
            trace = fig.data[0] if fig.data else None
            if request.chart_type == "hist":
                values   = [float(v) for v in chart_df.iloc[:, 0]] if not chart_df.empty else []
                datasets = [{"label": "Distribution", "data": values, "backgroundColor": "#6366f1", "borderColor": "#6366f1", "borderWidth": 1}]
            elif request.chart_type == "pie":
                labels   = [str(v) for v in trace.labels] if trace and hasattr(trace, "labels") and trace.labels is not None else []
                values   = [float(v) for v in trace.values] if trace and hasattr(trace, "values") and trace.values is not None else []
                datasets = _extract_datasets(fig, request.chart_type)
            else:
                labels   = [str(v) for v in trace.x] if trace and hasattr(trace, "x") and trace.x is not None else []
                values   = [float(v) for v in trace.y] if trace and hasattr(trace, "y") and trace.y is not None else []
                datasets = _extract_datasets(fig, request.chart_type)
        except Exception:
            pass

    return ChartResponse(
        chart_id   = result["chart_id"],
        file_id    = request.file_id,
        title      = result["title"],
        file_path  = result.get("file_path", ""),
        labels     = labels,
        values     = values,
        datasets   = datasets,
        chart_type = request.chart_type,
    )


# -- Report Generation ------------------------------------------------------

@router.get("/report/{file_id}", response_model=ReportResponse)
async def generate_file_report(
    file_id:      str,
    current_user: dict = Depends(get_current_user),
):
    cached = get_cached_file(file_id)
    if not cached:
        if not restore_file_from_disk(file_id):
            raise HTTPException(status_code=404, detail="File not found. Please re-upload.")
        cached = get_cached_file(file_id)

    file_name    = cached["file_data"].file_name
    exec_summary = get_executive_summary(file_id)
    table_map    = cached.get("table_map", {})

    result = generate_report(
        file_name    = file_name,
        file_id      = file_id,
        table_map    = table_map,
        exec_summary = exec_summary,
    )

    return ReportResponse(
        report_id = result["report_id"],
        file_id   = file_id,
        file_path = result["file_path"],
        timestamp = result["timestamp"],
    )


# -- Download Report --------------------------------------------------------

@router.get("/download/report/{report_id}")
async def download_report(report_id: str):
    from config import REPORTS_DIR
    file_path = os.path.join(REPORTS_DIR, f"{report_id}_report.md")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(path=file_path, filename=f"report_{report_id}.md", media_type="text/markdown")


# -- File Management --------------------------------------------------------

@router.get("/files", response_model=list[FileInfoResponse])
async def list_files(
    current_user: dict = Depends(get_current_user),
):
    files = get_all_business_files(user_id=current_user["user_id"])
    return [
        FileInfoResponse(
            file_id     = f["file_id"],
            file_name   = f["file_name"],
            file_type   = f["file_type"],
            sheet_names = f.get("sheet_names", []),
            row_count   = f.get("row_count", 0),
            col_count   = f.get("col_count", 0),
            uploaded_at = f["uploaded_at"],
            summary     = f.get("summary", ""),
        )
        for f in files
    ]


@router.get("/files/{file_id}", response_model=FileInfoResponse)
async def get_file_info(
    file_id:      str,
    current_user: dict = Depends(get_current_user),
):
    f = get_business_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")
    return FileInfoResponse(
        file_id     = f["file_id"],
        file_name   = f["file_name"],
        file_type   = f["file_type"],
        sheet_names = f.get("sheet_names", []),
        row_count   = f.get("row_count", 0),
        col_count   = f.get("col_count", 0),
        uploaded_at = f["uploaded_at"],
        summary     = f.get("summary", ""),
    )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id:      str,
    current_user: dict = Depends(get_current_user),
):
    f = get_business_file(file_id)
    if not f:
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        cached    = get_cached_file(file_id) or {}
        table_map = cached.get("table_map", {})
        if table_map:
            from services.sql_engine import drop_file_tables
            drop_file_tables(list(table_map.values()))
    except Exception as e:
        print(f"[WARN] Could not drop PostgreSQL tables: {e}")

    delete_business_file(file_id)

    from services.analyzer import _get_cache
    cache = _get_cache()
    cache.pop(file_id, None)

    from config import UPLOADS_DIR
    for fname in os.listdir(UPLOADS_DIR):
        if fname.startswith(file_id):
            try:
                os.remove(os.path.join(UPLOADS_DIR, fname))
            except Exception:
                pass

    return {"status": "deleted", "file_id": file_id}


# -- Analysis History -------------------------------------------------------

@router.get("/history/{file_id}")
async def get_history(
    file_id:      str,
    limit:        int = 10,
    offset:       int = 0,
    current_user: dict = Depends(get_current_user),
):
    import json as _json
    history = get_analysis_history(file_id, limit=limit, offset=offset, user_id=current_user["user_id"])
    for item in history:
        if item.get("chart_data"):
            try:
                item["chart_data"] = _json.loads(item["chart_data"])
            except Exception:
                item["chart_data"] = None
        else:
            item["chart_data"] = None
    return {"file_id": file_id, "history": history}