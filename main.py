"""
main.py

FastAPI application entry point.
Exposes both pipelines under separate prefixes:

    /api/v1/...  — PDF RAG pipeline
    /api/v2/...  — Business Intelligence pipeline (Excel/CSV)

Run with:
    uvicorn main:app --reload

API docs:
    http://localhost:8000/docs
    http://localhost:8000/redoc
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pipeline.db   import init_db
from pipeline.indexer import load_state
from routers.analyzer import router as data_router
from routers.rag      import router as rag_router

# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "AI Business Report Analyzer",
    description = """
## RAG — v2

Two complete AI pipelines in one API:

### 📄 PDF RAG Pipeline (`/api/v1`)
Upload research papers and PDFs. Ask questions with hybrid FAISS + BM25
retrieval, cross-encoder reranking, Groq Vision figure extraction,
and built-in evaluation.

### 📊 Data RAG Pipeline (`/api/v2`)
Upload Excel and CSV files. Get statistical analysis, anomaly detection,
auto chart generation, executive summaries, and downloadable reports.
    """,
    version     = "2.0.0",
)

# ── CORS ───────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Startup ────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    init_db()
    load_state()
    print("=" * 55)
    print("FastAPI ")
    print("  All docs     → http://localhost:8000/docs")
    print("=" * 55)

# ── Routes ─────────────────────────────────────────────────────────────────

app.include_router(rag_router,  prefix="/api/v1", tags=["📄 PDF RAG Pipeline"])
app.include_router(data_router, prefix="/api/v2", tags=["📊 Data RAG Pipeline"])

# ── Root ───────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {
        "name":      "AI Business Report Analyzer",
        "version":   "2.0.0",
        "pipelines": {
            "pdf_rag": {
                "prefix": "/api/v1",
                "docs":   "/api/v1/health",
            },
            "business_intelligence": {
                "prefix": "/api/v2",
                "docs":   "/api/v2/health",
            },
        },
        "swagger_ui": "/docs",
        "status":    "running",
    }
