
"""
models/schemas.py

Pydantic models for FastAPI request and response validation.
These define the shape of data going in and out of every API endpoint.
"""

from pydantic import BaseModel, Field
from typing import Optional


# -- Upload Response --------------------------------------------------------

class UploadResponse(BaseModel):
    """Returned after a successful file upload and processing."""
    file_id:     str
    file_name:   str
    file_type:   str
    status:      str
    sheet_names: list[str]
    shape:       tuple[int, int]   # (rows, cols)
    insights:    str
    anomaly_count: int


# -- Q&A Request / Response -------------------------------------------------

class QuestionRequest(BaseModel):
    """Sent by the client to ask a question about a file."""
    file_id:    str
    query:      str = Field(..., min_length=3, max_length=1000)
    sheet_name: Optional[str] = None

from typing import Any
class QuestionResponse(BaseModel):
    """Returned after answering a business question."""
    file_id:    str
    query:      str
    answer:     str
    follow_ups: list[str]
    sql:        str | None    = None
    chart:      dict | None   = None


# -- Summary Request / Response ---------------------------------------------

class SummaryRequest(BaseModel):
    """Request an executive summary for a file."""
    file_id: str


class SummaryResponse(BaseModel):
    """Returned executive summary."""
    file_id:  str
    summary:  str


# -- Chart Request / Response -----------------------------------------------

class ChartRequest(BaseModel):
    file_id:       str
    chart_type:    str = Field(..., pattern="^(bar|line|pie|hist|scatter)$")
    x_col:         str
    y_col:         Optional[str]       = None
    title:         Optional[str]       = ""
    color_col:     Optional[str]       = None
    sheet_name:    Optional[str]       = None
    aggregation:   str                 = "count"
    filter_col:    Optional[str]       = None
    filter_values: list[str]           = []


class ChartResponse(BaseModel):
    chart_id:   str
    file_id:    str
    title:      str
    file_path:  str = ""
    labels:     list = []
    values:     list = []
    datasets:   list = []
    chart_type: Optional[str] = None


# -- Anomaly Response -------------------------------------------------------

class AnomalyDetail(BaseModel):
    """Single anomaly detected in the dataset."""
    column:   str
    type:     str
    detail:   str
    severity: str   # 'high', 'medium', 'low'


class AnomalyResponse(BaseModel):
    """Returned anomaly list with AI explanation."""
    file_id:     str
    anomalies:   list[AnomalyDetail]
    explanation: str


# -- File Info Response -----------------------------------------------------

class FileInfoResponse(BaseModel):
    """Info about a registered business file."""
    file_id:     str
    file_name:   str
    file_type:   str
    sheet_names: list[str]
    row_count:   int
    col_count:   int
    uploaded_at: str
    summary:     str


# -- Report Response --------------------------------------------------------

class ReportResponse(BaseModel):
    """Returned after report generation."""
    report_id:  str
    file_id:    str
    file_path:  str
    timestamp:  str


# -- Health Check -----------------------------------------------------------

class HealthResponse(BaseModel):
    """Basic health check response."""
    status:  str
    version: str = "2.0"

# -- Auth -------------------------------------------------------------------
class UserResponse(BaseModel):
    user_id:   str
    email:     str
    name:      str
    auth_type: str
    avatar:    str = ""

class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserResponse