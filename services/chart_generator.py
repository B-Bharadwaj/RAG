"""
services/chart_generator.py

Generates Plotly charts from a DataFrame and saves them as HTML files.
Charts are stored in storage/charts/ and registered in SQLite.

Supported chart types:
    bar   — compare categories
    line  — show trends over time
    pie   — show distribution
    hist  — show distribution of numeric column
    scatter — show relationship between two numeric columns
"""

import os
import uuid
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from pipeline.db import save_chart
from config import CHARTS_DIR


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
        fig = _build_figure(df, chart_type, x_col, y_col, title, color_col)
        fig = _apply_dark_theme(fig)

        # Save as HTML
        chart_id  = str(uuid.uuid4())[:8]
        file_path = os.path.join(CHARTS_DIR, f"{chart_id}_{chart_type}.html")
        fig.write_html(file_path)

        # Register in DB
        save_chart(
            chart_id   = chart_id,
            file_id    = file_id,
            chart_type = chart_type,
            title      = title,
            file_path  = file_path,
        )

        return {
            "chart_id":  chart_id,
            "file_path": file_path,
            "title":     title,
            "fig":       fig,       # Plotly figure for direct Streamlit rendering
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
        return px.bar(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            text_auto=True,
        )

    elif chart_type == "line":
        return px.line(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            markers=True,
        )

    elif chart_type == "pie":
        # Aggregate and take top 10 for readability
        if y_col:
            agg = df.groupby(x_col)[y_col].sum().reset_index()
            agg = agg.nlargest(10, y_col)
            return px.pie(agg, names=x_col, values=y_col, title=title)
        else:
            counts = df[x_col].value_counts().head(10).reset_index()
            counts.columns = [x_col, "count"]
            return px.pie(counts, names=x_col, values="count", title=title)

    elif chart_type == "hist":
        return px.histogram(
            df, x=x_col,
            title=title, nbins=30,
        )

    elif chart_type == "scatter":
        return px.scatter(
            df, x=x_col, y=y_col,
            title=title, color=color_col,
            opacity=0.6,
        )

    else:
        raise ValueError(f"Unsupported chart type: '{chart_type}'")


def _apply_dark_theme(fig) -> go.Figure:
    """Apply dark theme matching the Streamlit UI."""
    fig.update_layout(
        paper_bgcolor = "#0a0a0a",
        plot_bgcolor  = "#111111",
        font          = dict(color="#e5e5e5", family="Inter, sans-serif"),
        title         = dict(font=dict(size=16, color="#ffffff")),
        xaxis         = dict(gridcolor="#1f1f1f", linecolor="#2a2a2a"),
        yaxis         = dict(gridcolor="#1f1f1f", linecolor="#2a2a2a"),
        legend        = dict(bgcolor="#111111", bordercolor="#2a2a2a"),
        margin        = dict(l=40, r=40, t=60, b=40),
    )
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

    # Bar chart — top categorical vs first numeric
    if categorical_cols and numeric_cols:
        suggestions.append({
            "chart_type": "bar",
            "x_col":      categorical_cols[0],
            "y_col":      numeric_cols[0],
            "title":      f"Top {categorical_cols[0]} by {numeric_cols[0]}",
        })

    # Pie chart — distribution of first categorical
    if categorical_cols:
        suggestions.append({
            "chart_type": "pie",
            "x_col":      categorical_cols[0],
            "y_col":      numeric_cols[0] if numeric_cols else None,
            "title":      f"Distribution of {categorical_cols[0]}",
        })

    # Histogram — first numeric column
    if numeric_cols:
        suggestions.append({
            "chart_type": "hist",
            "x_col":      numeric_cols[0],
            "y_col":      None,
            "title":      f"Distribution of {numeric_cols[0]}",
        })

    # Scatter — first two numeric columns
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
    "orders by", "quantity by",
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
    query: str,
    df: pd.DataFrame,
    file_id: str,
    file_name: str,
    groq_client,
    model: str,
) -> dict | None:
    """
    Full pipeline for auto chart generation inside chat.

    1. Pick best columns using Groq
    2. Generate Plotly chart
    3. Return fig for inline rendering

    Returns None if no chart is appropriate.
    """
    # Step 1 — pick columns
    chart_config = pick_chart_columns(query, df, groq_client, model)
    if not chart_config:
        return None

    # Step 2 — generate chart
    result = generate_chart(
        df         = df,
        chart_type = chart_config["chart_type"],
        x_col      = chart_config["x_col"],
        y_col      = chart_config["y_col"],
        file_id    = file_id,
        file_name  = file_name,
        title      = chart_config["title"],
    )

    if "error" in result and result["error"]:
        print(f"[chat_chart] Chart generation failed: {result['error']}")
        return None

    return result
