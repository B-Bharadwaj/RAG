"""
pipeline/processor.py

Lightweight file processor for the v3 pipeline.

v3 changes:
    - Statistical analysis removed - replaced by SQL queries on PostgreSQL
    - IQR anomaly detection removed - replaced by SQL anomaly queries
    - Context compression removed - schema extracted directly from PostgreSQL
    - Only keeps basic shape/type info needed for fallback and UI display
"""

import pandas as pd
from pipeline.loader import FileData

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


def process_file(
    file_data:  FileData,
    sheet_name: str = None,
) -> dict:
    """
    Lightweight processing - extracts only basic metadata.
    All heavy analysis (stats, anomalies, summaries) now done via SQL.

    Returns:
        shape     -> (rows, cols) tuple
        columns   -> list of column names
        dtypes    -> dict of column -> dtype
        summary   -> empty dict (kept for backward compatibility)
        anomalies -> empty list (kept for backward compatibility)
        context   -> minimal context string for fallback LLM calls
    """
    sheet = sheet_name or file_data.sheet_names[0]
    df    = file_data.dataframes.get(sheet)

    if df is None:
        return {
            "shape":    [0, 0],
            "columns":  [],
            "dtypes":   {},
            "summary":  {},
            "anomalies":[],
            "context":  "",
        }

    # Basic shape info
    rows, cols = df.shape
    columns    = list(df.columns)
    dtypes     = {col: str(df[col].dtype) for col in columns}

    # Minimal context string - used only as fallback if PostgreSQL is down
    col_summary = []
    for col in columns[:10]:   # cap at 10 columns
        dtype = str(df[col].dtype)
        if "int" in dtype or "float" in dtype:
            col_summary.append(
                f"{col} (numeric): "
                f"min={df[col].min()}, max={df[col].max()}, "
                f"mean={df[col].mean():.2f}"
            )
        else:
            top = df[col].value_counts().head(3).index.tolist()
            col_summary.append(f"{col} (text): top values = {top}")

    context = (
        f"File: {file_data.file_name}\n"
        f"Rows: {rows:,} | Columns: {cols}\n"
        f"Sheet: {sheet}\n\n"
        + "\n".join(col_summary)
    )

    log.info(
        "Processed file: %s - %d rows   %d cols",
        file_data.file_name, rows, cols,
    )

    return {
        "shape":     [rows, cols],
        "columns":   columns,
        "dtypes":    dtypes,
        "summary":   {},       # empty - SQL handles this now
        "anomalies": [],       # empty - SQL handles this now
        "context":   context,  # minimal fallback only
    }


