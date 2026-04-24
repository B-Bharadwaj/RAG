"""
pipeline/processor.py

The Pandas analysis brain of v2.

Takes a FileData object and produces:
1. A compressed text context  → sent to Groq for Q&A
2. Statistical summary        → shown in UI and used for insights
3. Anomaly detection          → flags unusual values
4. Column profile             → data types, nulls, unique counts

This is what makes v2 different from v1 — instead of just chunking text,
we actually understand the structure and statistics of the data.
"""

import pandas as pd
import numpy as np
from pipeline.loader import FileData
from config import MAX_CONTEXT_CHARS, MAX_SAMPLE_ROWS


# ── Main entry point ───────────────────────────────────────────────────────

def process_file(file_data: FileData, sheet_name: str = None) -> dict:
    """
    Master processor — routes to correct handler based on file type.

    Parameters
    ----------
    file_data  : FileData object from loader.py
    sheet_name : which sheet to process (Excel only). None = first sheet.

    Returns
    -------
    dict with keys:
        context       : str  — compressed text context for Groq
        summary       : dict — statistical summary
        anomalies     : list — detected anomalies
        column_profile: list — per column metadata
        shape         : tuple — (rows, cols)
        sheet_name    : str  — which sheet was processed
    """
    if file_data.file_type == "pdf":
        return _process_pdf(file_data)
    elif file_data.file_type in ("excel", "csv"):
        return _process_tabular(file_data, sheet_name)
    else:
        raise ValueError(f"Unknown file type: {file_data.file_type}")


# ── PDF Processor ──────────────────────────────────────────────────────────

def _process_pdf(file_data: FileData) -> dict:
    """
    For PDFs we just join all page text into a context string.
    The actual RAG pipeline handles retrieval — this is just for
    cases where we want a quick summary context.
    """
    all_text = "\n\n".join(
        f"[Page {page_num}]\n{text}"
        for page_num, text in file_data.pages
    )
    context = all_text[:MAX_CONTEXT_CHARS]

    return {
        "context":        context,
        "summary":        {"type": "pdf", "pages": len(file_data.pages)},
        "anomalies":      [],
        "column_profile": [],
        "shape":          (len(file_data.pages), 0),
        "sheet_name":     "pdf",
    }


# ── Tabular Processor ──────────────────────────────────────────────────────

def _process_tabular(file_data: FileData, sheet_name: str = None) -> dict:
    """
    Full analysis pipeline for Excel and CSV files.
    """
    # Pick the right sheet
    if sheet_name is None or sheet_name not in file_data.dataframes:
        sheet_name = file_data.sheet_names[0]

    df = file_data.dataframes[sheet_name]

    # Run all analysis steps
    summary        = _build_summary(df, file_data.file_name, sheet_name)
    column_profile = _build_column_profile(df)
    anomalies      = _detect_anomalies(df)
    context        = _build_context(df, summary, anomalies, file_data.file_name, sheet_name)

    return {
        "context":        context,
        "summary":        summary,
        "anomalies":      anomalies,
        "column_profile": column_profile,
        "shape":          (len(df), len(df.columns)),
        "sheet_name":     sheet_name,
    }


# ── Summary Builder ────────────────────────────────────────────────────────

def _build_summary(df: pd.DataFrame, file_name: str, sheet_name: str) -> dict:
    """
    Build a statistical summary of the DataFrame.
    Separates numeric columns from categorical columns.
    """
    numeric_cols     = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["str", "category"]).columns.tolist()
    date_cols        = df.select_dtypes(include=["datetime64"]).columns.tolist()

    summary = {
        "file_name":       file_name,
        "sheet_name":      sheet_name,
        "total_rows":      len(df),
        "total_columns":   len(df.columns),
        "columns":         list(df.columns),
        "numeric_cols":    numeric_cols,
        "categorical_cols":categorical_cols,
        "date_cols":       date_cols,
        "null_counts":     df.isnull().sum().to_dict(),
        "numeric_stats":   {},
        "categorical_stats":{},
    }

    # Numeric stats
    for col in numeric_cols:
        try:
            summary["numeric_stats"][col] = {
                "min":    round(float(df[col].min()), 2),
                "max":    round(float(df[col].max()), 2),
                "mean":   round(float(df[col].mean()), 2),
                "median": round(float(df[col].median()), 2),
                "std":    round(float(df[col].std()), 2),
                "sum":    round(float(df[col].sum()), 2),
            }
        except Exception:
            pass

    # Categorical stats
    for col in categorical_cols:
        try:
            vc = df[col].value_counts()
            summary["categorical_stats"][col] = {
                "unique_count": int(df[col].nunique()),
                "top_5":        vc.head(5).to_dict(),
                "most_common":  str(vc.index[0]) if len(vc) > 0 else "N/A",
            }
        except Exception:
            pass

    return summary


# ── Column Profile ─────────────────────────────────────────────────────────

def _build_column_profile(df: pd.DataFrame) -> list[dict]:
    """
    Per column metadata — data type, null count, unique count, sample values.
    Used by the UI to show a column overview table.
    """
    profile = []
    for col in df.columns:
        try:
            null_count  = int(df[col].isnull().sum())
            unique_count= int(df[col].nunique())
            dtype       = str(df[col].dtype)
            sample_vals = df[col].dropna().head(3).tolist()
            sample_vals = [str(v) for v in sample_vals]

            profile.append({
                "column":       col,
                "dtype":        dtype,
                "null_count":   null_count,
                "null_pct":     round(null_count / len(df) * 100, 1) if len(df) > 0 else 0,
                "unique_count": unique_count,
                "sample_values":sample_vals,
            })
        except Exception:
            pass
    return profile


# ── Anomaly Detection ──────────────────────────────────────────────────────

def _detect_anomalies(df: pd.DataFrame) -> list[dict]:
    """
    Detect anomalies in numeric columns using IQR method.
    Also flags columns with high null rates.

    Returns list of anomaly dicts — each has:
        column  : column name
        type    : 'outlier' | 'high_nulls' | 'negative_values'
        detail  : human readable description
        severity: 'high' | 'medium' | 'low'
    """
    anomalies = []
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) < 10:
            continue

        # IQR outlier detection
        try:
            Q1  = series.quantile(0.25)
            Q3  = series.quantile(0.75)
            IQR = Q3 - Q1
            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR

            outliers = series[(series < lower) | (series > upper)]
            if len(outliers) > 0:
                pct = round(len(outliers) / len(series) * 100, 1)
                anomalies.append({
                    "column":   col,
                    "type":     "outlier",
                    "detail":   (
                        f"{len(outliers)} outliers ({pct}%) detected in '{col}'. "
                        f"Expected range: [{round(lower,2)}, {round(upper,2)}]. "
                        f"Max value: {round(float(series.max()),2)}"
                    ),
                    "severity": "high" if pct > 5 else "medium",
                })
        except Exception:
            pass

        # Negative values check (for columns that shouldn't be negative)
        try:
            col_lower = col.lower()
            if any(kw in col_lower for kw in ["price", "revenue", "sales", "amount", "cost", "quantity", "qty"]):
                neg_count = int((series < 0).sum())
                if neg_count > 0:
                    anomalies.append({
                        "column":   col,
                        "type":     "negative_values",
                        "detail":   f"{neg_count} negative values in '{col}' — possible data quality issue.",
                        "severity": "high",
                    })
        except Exception:
            pass

    # High null rate check
    for col in df.columns:
        try:
            null_pct = df[col].isnull().sum() / len(df) * 100
            if null_pct > 20:
                anomalies.append({
                    "column":   col,
                    "type":     "high_nulls",
                    "detail":   f"'{col}' has {round(null_pct,1)}% missing values.",
                    "severity": "medium" if null_pct < 50 else "high",
                })
        except Exception:
            pass

    return anomalies


# ── Context Builder ────────────────────────────────────────────────────────

def _build_context(
    df: pd.DataFrame,
    summary: dict,
    anomalies: list,
    file_name: str,
    sheet_name: str,
) -> str:
    """
    Build a compressed text context to send to Groq.

    Key insight: we NEVER send raw rows to the LLM.
    Instead we send a smart statistical summary — this keeps
    token usage low while giving the LLM everything it needs.
    """
    lines = []

    # Header
    lines.append(f"DATASET: {file_name} | Sheet: {sheet_name}")
    lines.append(f"SHAPE: {summary['total_rows']:,} rows × {summary['total_columns']} columns")
    lines.append(f"COLUMNS: {', '.join(summary['columns'])}")
    lines.append("")

    # Numeric stats
    if summary["numeric_stats"]:
        lines.append("NUMERIC COLUMN STATISTICS:")
        for col, stats in summary["numeric_stats"].items():
            lines.append(
                f"  {col}: min={stats['min']}, max={stats['max']}, "
                f"mean={stats['mean']}, median={stats['median']}, "
                f"sum={stats['sum']}, std={stats['std']}"
            )
        lines.append("")

    # Categorical stats
    if summary["categorical_stats"]:
        lines.append("CATEGORICAL COLUMN STATISTICS:")
        for col, stats in summary["categorical_stats"].items():
            top = ", ".join(f"{k}({v})" for k, v in list(stats["top_5"].items())[:3])
            lines.append(
                f"  {col}: {stats['unique_count']} unique values. "
                f"Top values: {top}"
            )
        lines.append("")

    # Sample rows
    lines.append(f"SAMPLE ROWS (first {MAX_SAMPLE_ROWS}):")
    lines.append(df.head(MAX_SAMPLE_ROWS).to_string(index=False))
    lines.append("")

    # Anomalies
    if anomalies:
        lines.append("DETECTED ANOMALIES:")
        for a in anomalies:
            lines.append(f"  [{a['severity'].upper()}] {a['detail']}")
        lines.append("")

    # Null summary
    null_cols = {k: v for k, v in summary["null_counts"].items() if v > 0}
    if null_cols:
        lines.append("MISSING VALUES:")
        for col, count in null_cols.items():
            lines.append(f"  {col}: {count} missing")

    context = "\n".join(lines)

    # Trim to max chars
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n... [truncated]"

    return context


# ── Quick test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pipeline.loader import load_file

    if len(sys.argv) < 2:
        print("Usage: python pipeline/processor.py <file>")
        sys.exit(1)

    path     = sys.argv[1]
    name     = __import__("os").path.basename(path)
    filedata = load_file(path, name)
    result   = process_file(filedata)

    print(f"\nShape    : {result['shape']}")
    print(f"Sheet    : {result['sheet_name']}")
    print(f"Anomalies: {len(result['anomalies'])}")
    print(f"\nContext preview:\n{result['context'][:800]}")
    print(f"\nAnomalies found:")
    for a in result["anomalies"]:
        print(f"  [{a['severity']}] {a['detail']}")
