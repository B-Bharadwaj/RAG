"""
services/chart_generator.py

Generates Plotly charts from a DataFrame and saves them as HTML files.
Charts are stored in storage/charts/ and registered in SQLite.

Supported chart types:
    bar   - compare categories
    line  - show trends over time
    pie   - show distribution
    hist  - show distribution of numeric column
    scatter - show relationship between two numeric columns
"""

import os
import uuid
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import logging
from services.sql_engine import save_chart
from config import CHARTS_DIR

log = logging.getLogger(__name__)
def _extract_specific_values(question: str, df) -> dict:
    """
    Scan the question for specific values that exist in DataFrame columns.

    e.g. question = "Compare Bangalore vs Pune employees"
         City column has ["Bangalore", "Pune", "New Delhi"]
         returns {"City": ["Bangalore", "Pune"]}

    This tells the SQL prompt exactly which values to filter on
    instead of aggregating the entire column.
    """
    import re
    found = {}

    if df is None:
        return found

    question_lower = question.lower()

    for col in df.columns:
        dtype = str(df[col].dtype)

        # Only scan text/categorical columns
        if "int" in dtype or "float" in dtype:
            continue

        unique_vals = df[col].dropna().unique().tolist()

        # Only scan columns with reasonable number of unique values
        if len(unique_vals) > 200:
            continue

        matched = []
        for val in unique_vals:
            val_str = str(val).strip()
            if len(val_str) < 2:
                continue
            # Check if this value appears in the question
            if val_str.lower() in question_lower:
                matched.append(val_str)

        if matched:
            found[col] = matched

    return found

def generate_chart(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str = None,
    file_id: str = "",
    file_name: str = "",
    title: str = "",
    color_col: str = None,
) -> dict:
    """
    Generate a Plotly chart and save as HTML.

    Parameters
    ----------
    df         : DataFrame to plot
    chart_type : 'bar', 'line', 'pie', 'hist', 'scatter'
    x_col      : column for x axis (or labels for pie)
    y_col      : column for y axis (or values for pie)
    file_id    : parent file ID for DB registration
    file_name  : used in chart title
    title      : chart title (auto generated if empty)
    color_col  : optional column to use for color grouping

    Returns
    -------
    dict with chart_id, file_path, title
    """
    if title == "":
        title = _auto_title(chart_type, x_col, y_col, file_name)

    try:
        fig, processed_df = _build_figure(df, chart_type, x_col, y_col, title, color_col)
        fig = _apply_clean_theme(fig)

        chart_id  = str(uuid.uuid4())[:8]
        file_path = ""

        # Register in DB
        save_chart(
            chart_id   = chart_id,
            file_id    = file_id,
            chart_type = chart_type,
            title      = title,
            file_path  = file_path,
        )

        return {
            "chart_id":   chart_id,
            "file_path":  file_path,
            "title":      title,
            "fig":        fig,       # Plotly figure for direct Streamlit rendering
            "data":       processed_df.to_dict(orient="records") if processed_df is not None else [],
            "chart_type": chart_type,
            "x_column":   x_col,
            "y_column":   y_col,
        }

    except Exception as e:
        return {"error": str(e), "chart_id": None, "file_path": None}


def _build_figure(
    df: pd.DataFrame,
    chart_type: str,
    x_col: str,
    y_col: str,
    title: str,
    color_col: str,
):
    """Build the correct Plotly figure based on chart type."""

    if chart_type == "bar":
        # Aggregate if too many x values
        if df[x_col].nunique() > 20:
            df = df.groupby(x_col)[y_col].sum().reset_index()
            df = df.nlargest(20, y_col)
        fig = px.bar(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            barmode='group' if color_col else 'relative'
            # text_auto=True
        )
        return fig, df

    elif chart_type == "line":
        fig = px.line(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            markers=True,
        )
        return fig, df

    elif chart_type == "pie":
        # Aggregate and take top 10 for readability
        if y_col:
            agg = df.groupby(x_col)[y_col].sum().reset_index()
            agg = agg.nlargest(10, y_col)
            fig = px.pie(agg, names=x_col, values=y_col, title=title)
            return fig, agg
        else:
            counts = df[x_col].value_counts().head(10).reset_index()
            counts.columns = [x_col, "count"]
            fig = px.pie(counts, names=x_col, values="count", title=title)
            return fig, counts

    elif chart_type == "hist":
        fig = px.histogram(
            df, x=x_col,
            title=title, nbins=30,
        )
        return fig, df

    elif chart_type == "scatter":
        fig = px.scatter(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            opacity=0.6,
        )
        return fig, df

    else:
        raise ValueError(f"Unsupported chart type: '{chart_type}'")


def _apply_clean_theme(fig) -> go.Figure:
    """Apply a clean, modern, vibrant theme matching the frontend UI."""
    fig.update_layout(
        paper_bgcolor = "rgba(0,0,0,0)",
        plot_bgcolor  = "rgba(0,0,0,0)",
        font          = dict(color="#475569", family="Inter, sans-serif"),
        title         = dict(font=dict(size=18, color="#1e293b", family="Inter, sans-serif")),
        xaxis         = dict(gridcolor="#e2e8f0", linecolor="#cbd5e1", zeroline=False, tickfont=dict(color="#64748b")),
        yaxis         = dict(gridcolor="#e2e8f0", linecolor="#cbd5e1", zeroline=False, tickfont=dict(color="#64748b")),
        legend        = dict(bgcolor="rgba(255,255,255,0.8)", bordercolor="#e2e8f0", borderwidth=1),
        margin        = dict(l=40, r=40, t=60, b=40),
        colorway      = ["#6366f1", "#ec4899", "#14b8a6", "#f59e0b", "#8b5cf6", "#10b981", "#ef4444", "#3b82f6"]
    )
    
    # Give charts a cleaner look by removing unnecessary trace borders
    fig.update_traces(marker=dict(line=dict(width=0)))
    
    return fig


def _auto_title(
    chart_type: str,
    x_col: str,
    y_col: str,
    file_name: str,
) -> str:
    """Generate a chart title automatically."""
    titles = {
        "bar":     f"{y_col} by {x_col}",
        "line":    f"{y_col} over {x_col}",
        "pie":     f"Distribution of {x_col}",
        "hist":    f"Distribution of {x_col}",
        "scatter": f"{x_col} vs {y_col}",
    }
    return titles.get(chart_type, f"{chart_type} chart")


def get_suggested_charts(df: pd.DataFrame) -> list[dict]:
    """
    Suggest relevant charts based on the DataFrame's column types.
    Called automatically after file upload to pre-generate useful charts.

    Returns list of chart config dicts.
    """
    suggestions = []
    numeric_cols     = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()

    # Bar chart - top categorical vs first numeric
    if categorical_cols and numeric_cols:
        suggestions.append({
            "chart_type": "bar",
            "x_col":      categorical_cols[0],
            "y_col":      numeric_cols[0],
            "title":      f"Top {categorical_cols[0]} by {numeric_cols[0]}",
        })

    # Pie chart - distribution of first categorical
    if categorical_cols:
        suggestions.append({
            "chart_type": "pie",
            "x_col":      categorical_cols[0],
            "y_col":      numeric_cols[0] if numeric_cols else None,
            "title":      f"Distribution of {categorical_cols[0]}",
        })

    # Histogram - first numeric column
    if numeric_cols:
        suggestions.append({
            "chart_type": "hist",
            "x_col":      numeric_cols[0],
            "y_col":      None,
            "title":      f"Distribution of {numeric_cols[0]}",
        })

    # Scatter - first two numeric columns
    if len(numeric_cols) >= 2:
        suggestions.append({
            "chart_type": "scatter",
            "x_col":      numeric_cols[0],
            "y_col":      numeric_cols[1],
            "title":      f"{numeric_cols[0]} vs {numeric_cols[1]}",
        })

    return suggestions

# ===========================================================================
# Auto chart detection and column picking for chat
# ===========================================================================

CHART_KEYWORDS = {
    "trend", "over time", "by month", "by year", "by week",
    "compare", "comparison", "distribution", "breakdown",
    "top", "highest", "lowest", "best", "worst",
    "per", "by region", "by country", "by category",
    "by product", "by segment", "chart", "plot",
    "visualize", "show me", "graph", "how much",
    "how many", "which", "sales over", "revenue over",
    "orders by", "quantity by","separately", "each", "per city", "per region", "per category",
    "average", "total", "between", "versus", "vs", "difference",
}


def needs_chart(query: str) -> bool:
    """
    Detect if a question is chart-worthy.
    Returns True if the query is asking for a visual comparison,
    trend, distribution, or ranking.
    """
    q = query.lower()
    return any(kw in q for kw in CHART_KEYWORDS)


def pick_chart_columns(
    query: str,
    df: pd.DataFrame,
    groq_client,
    model: str,
) -> dict | None:
    """
    Ask Groq to pick the best chart type and columns
    based on the user's question and available columns.

    Parameters
    ----------
    query       : user's question
    df          : the active DataFrame
    groq_client : Groq client instance
    model       : model name to use

    Returns
    -------
    dict with keys: chart_type, x_col, y_col (or None on failure)
    """
    import json as _json
    import time as _time

    numeric_cols     = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object"]).columns.tolist()
    all_cols         = list(df.columns)

    prompt = f"""\
You are a data visualization expert. Based on the user's question and available columns,
pick the best chart type and columns to visualize the answer.

USER QUESTION: {query}

AVAILABLE COLUMNS: {all_cols}
NUMERIC COLUMNS: {numeric_cols}
CATEGORICAL COLUMNS: {categorical_cols}

Rules:
- bar   : comparing categories (e.g. sales by country)
- line  : trends over time (e.g. revenue over months)
- pie   : distribution/share (e.g. orders by category)
- hist  : distribution of one numeric column
- scatter: relationship between two numeric columns

Return ONLY a valid JSON object, no explanation, no markdown:
{{
  "chart_type": "bar" or "line" or "pie" or "hist" or "scatter",
  "x_col": "<column name from available columns>",
  "y_col": "<column name from available columns or null>",
  "title": "<short chart title under 8 words>"
}}

If no chart makes sense, return: {{"chart_type": null}}
"""

    try:
        _time.sleep(1)
        response = groq_client.chat.completions.create(
            model      = model,
            messages   = [{"role": "user", "content": prompt}],
            max_tokens = 150,
            temperature= 0.0,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if raw.startswith("```"):
            parts = raw.split("```")
            raw   = parts[1] if len(parts) > 1 else raw
            if raw.lower().startswith("json"):
                raw = raw[4:]

        result = _json.loads(raw.strip())

        # Validate chart_type
        if not result.get("chart_type"):
            return None

        # Validate columns exist in DataFrame
        x_col = result.get("x_col")
        y_col = result.get("y_col")

        if x_col not in df.columns:
            return None
        if y_col and y_col not in df.columns:
            y_col = None

        return {
            "chart_type": result["chart_type"],
            "x_col":      x_col,
            "y_col":      y_col,
            "title":      result.get("title", ""),
        }

    except Exception as e:
        print(f"[chart_picker] Failed: {e}")
        return None


def generate_chat_chart(
    query:     str,
    df,
    file_id:   str,
    file_name: str,
    **kwargs,
) -> dict | None:
    """
    Generate a specific chart from a natural language query using SQL.

    New flow:
        1. Extract specific values mentioned in the question
        2. Get schema from PostgreSQL
        3. LLM generates specific SQL + chart config
        4. SQL runs on PostgreSQL -> exact filtered data
        5. Convert result to DataFrame
        6. Plotly renders chart
    """
    import pandas as pd
    from services.sql_engine  import get_schema, execute_sql
    from generation.generator import generate_sql_chart_query

    try:
        # Get cached table_map
        from services.analyzer import get_cached_file
        cached    = get_cached_file(file_id)
        table_map = cached.get("table_map", {}) if cached else {}

        if not table_map:
            return _legacy_generate_chat_chart(
                query     = query,
                df        = df,
                file_id   = file_id,
                file_name = file_name,
            )

        # Step 1 - extract specific values from question
        specific_values = _extract_specific_values(query, df)
        log.info(
            "Chart specific values detected: %s",
            specific_values or "none"
        )

        # Step 2 - get schema
        table_names = list(table_map.values())
        schema      = get_schema(table_names)

        # Step 3 - LLM generates specific SQL
        chart_config = generate_sql_chart_query(
            question        = query,
            schema          = schema,
            specific_values = specific_values,
        )

        if not chart_config or chart_config.get("sql") == "NOT_SQL":
            return None

        # Step 4 - execute SQL on PostgreSQL
        sql    = chart_config["sql"]
        result = execute_sql(sql)

        if not result["success"] or not result["rows"]:
            log.warning("Chart SQL returned no results: %s", sql)
            return None

        # Step 5 - convert to DataFrame
        chart_df   = pd.DataFrame(
            result["rows"],
            columns = result["columns"]
        )
        chart_type = chart_config.get("chart_type", "bar")
        x_col      = chart_config.get("x_col", result["columns"][0])
        y_col      = chart_config.get(
            "y_col",
            result["columns"][1] if len(result["columns"]) > 1 else None
        )
        title = chart_config.get("title", query[:50])
        color_col = chart_config.get("color_col")
        if color_col in ["", "null", "None"]:
            color_col = None

        log.info(
            "Chart generated - type=%s x=%s y=%s color=%s rows=%d",
            chart_type, x_col, y_col, color_col, len(chart_df)
        )

        # Step 6 - generate chart
        return generate_chart(
            df         = chart_df,
            chart_type = chart_type,
            x_col      = x_col,
            y_col      = y_col,
            file_id    = file_id,
            file_name  = file_name,
            title      = title,
            color_col  = color_col,
        )

    except Exception as e:
        log.warning("SQL chart generation failed: %s", e)
        return None