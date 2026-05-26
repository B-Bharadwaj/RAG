"""
services/report_generator.py

SQL-driven report generation for v3.
All content comes from PostgreSQL queries - no Pandas stats.
"""

import os
import uuid
from datetime import datetime, timezone
from config import REPORTS_DIR


def generate_report(
    file_name:   str,
    file_id:     str,
    table_map:   dict,
    exec_summary: str = "",
) -> dict:
    """
    Generate a full markdown report using SQL queries on PostgreSQL.

    Steps:
        1. Get schema from PostgreSQL
        2. Run 5 summary SQL queries
        3. Run 4 anomaly SQL queries
        4. Build markdown from real results
        5. Save to disk and return report_id

    Returns:
        report_id, file_path, timestamp
    """
    from services.sql_engine    import get_schema, execute_sql
    from generation.generator   import (
        generate_summary_queries,
        generate_anomaly_queries,
        generate_sql_summary,
        generate_sql_anomaly_explanation,
    )

    report_id  = str(uuid.uuid4())[:8]
    timestamp  = datetime.now(timezone.utc).isoformat()
    table_names = list(table_map.values())

    # -- Get schema ---------------------------------------------------------
    schema = get_schema(table_names) if table_names else ""

    # -- Run summary queries ------------------------------------------------
    summary_results = ""
    if schema:
        queries = generate_summary_queries(schema)
        for i, sql in enumerate(queries, 1):
            try:
                result = execute_sql(sql)
                if result["success"] and result["rows"]:
                    summary_results += (
                        f"Query {i}: {sql}\n"
                        f"Result: {result['rows'][:5]}\n\n"
                    )
            except Exception:
                pass

    # -- Run anomaly queries ------------------------------------------------
    anomaly_results = ""
    if schema:
        anomaly_queries = generate_anomaly_queries(schema)
        for i, sql in enumerate(anomaly_queries, 1):
            try:
                result = execute_sql(sql)
                if result["success"]:
                    anomaly_results += (
                        f"Check {i}: {sql}\n"
                        f"Result: {result['rows'][:5]}\n\n"
                    )
            except Exception:
                pass

    # -- Generate SQL summary if not provided -------------------------------
    if not exec_summary and summary_results:
        exec_summary = generate_sql_summary(
            file_name = file_name,
            schema    = schema,
            results   = summary_results,
        )

    # -- Generate anomaly explanation ---------------------------------------
    anomaly_explanation = ""
    if anomaly_results:
        from generation.generator import generate_sql_anomaly_explanation
        anomaly_explanation = generate_sql_anomaly_explanation(
            file_name = file_name,
            results   = anomaly_results,
        )

    # -- Build markdown report ----------------------------------------------
    lines = []
    lines.append(f"# Business Intelligence Report")
    lines.append(f"**File:** {file_name}")
    lines.append(f"**Generated:** {timestamp[:19].replace('T', ' ')} UTC")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    if exec_summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(exec_summary)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Key Findings from SQL

    lines = []
    lines.append(f"# Business Intelligence Report")
    lines.append(f"**File:** {file_name}")
    lines.append(f"**Generated:** {timestamp[:19].replace('T', ' ')} UTC")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary - main content
    if exec_summary:
        lines.append(exec_summary)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Data Quality
    if anomaly_explanation:
        lines.append("## Data Quality Analysis")
        lines.append("")
        lines.append(anomaly_explanation)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Schema info - collapsed at bottom
    if schema:
        lines.append("## Dataset Schema")
        lines.append("")
        lines.append("```")
        lines.append(schema[:500])
        lines.append("```")
        lines.append("")

    # Data Quality
    if anomaly_explanation:
        lines.append("## Data Quality Analysis")
        lines.append("")
        lines.append(anomaly_explanation)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Schema info
    if schema:
        lines.append("## Dataset Schema")
        lines.append("")
        lines.append("```")
        lines.append(schema[:1000])
        lines.append("```")
        lines.append("")

    report_content = "\n".join(lines)

    # -- Save to disk -------------------------------------------------------
    os.makedirs(REPORTS_DIR, exist_ok=True)
    file_path = os.path.join(REPORTS_DIR, f"{report_id}_report.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    return {
        "report_id": report_id,
        "file_path": file_path,
        "timestamp": timestamp,
    }