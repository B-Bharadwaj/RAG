"""
config.py

All configuration loaded from environment variables via .env file.
No secrets are hardcoded here.

v2 additions:
    - GROQ_MODEL_LARGE / GROQ_MODEL_SMALL  (model routing)
    - MAX_SAMPLE_ROWS / MAX_CONTEXT_CHARS  (Pandas context limits)
    - REPORTS_DIR / CHARTS_DIR / UPLOADS_DIR (new storage paths)
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Read a required env var - crash early with a clear message if missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env to this folder and fill in your values."
        )
    return value


# -- API Keys ---------------------------------------------------------------
GROQ_API_KEY = _require("GROQ_API_KEY")

# -- Upload Limits ----------------------------------------------------------
MAX_FILE_SIZE_MB    = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_PAGE_COUNT      = int(os.getenv("MAX_PAGE_COUNT",   "100"))

# -- Rate Limiting ----------------------------------------------------------
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "20"))

# -- Model Names ------------------------------------------------------------
GROQ_MODEL_NAME     = "llama-3.1-8b-instant"           # generation (fast)
GROQ_MODEL_LARGE    = "llama-3.3-70b-versatile"        # complex Q&A, anomaly detection
GROQ_MODEL_SMALL    = "llama-3.1-8b-instant"           # summaries, simple tasks
GROQ_VISION_MODEL   = "meta-llama/llama-4-scout-17b-16e-instruct"
EMBED_MODEL_NAME    = "all-MiniLM-L6-v2"
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# -- Chunking (for PDF text) ------------------------------------------------
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 200

# -- Retrieval --------------------------------------------------------------
TOP_K            = 5
RERANK_THRESHOLD = 0.5

# -- FAISS ------------------------------------------------------------------
HNSW_NEIGHBORS       = 32
HNSW_EF_CONSTRUCTION = 200

# -- Parallel OCR -----------------------------------------------------------
OCR_MAX_WORKERS = 4

# -- Deduplication ----------------------------------------------------------
DEDUP_COSINE_THRESHOLD = 0.95

# -- Chat Memory ------------------------------------------------------------
MAX_HISTORY_TURNS = 4        # only last 4 messages sent to Groq - saves tokens

# -- Pandas Context ---------------------------------------------------------
MAX_SAMPLE_ROWS   = 5        # rows shown to LLM as sample
MAX_CONTEXT_CHARS = 3000     # max chars of data context sent per request

# -- Paths ------------------------------------------------------------------
STORAGE_DIR      = "storage"
FAISS_INDEX_PATH = os.path.join(STORAGE_DIR, "index.faiss")
METADATA_PATH    = os.path.join(STORAGE_DIR, "metadata.pkl")
BM25_PATH        = os.path.join(STORAGE_DIR, "bm25.pkl")
DB_PATH          = os.path.join(STORAGE_DIR, "registry.db")
REPORTS_DIR      = os.path.join(STORAGE_DIR, "reports")
CHARTS_DIR       = os.path.join(STORAGE_DIR, "charts")
UPLOADS_DIR      = os.path.join(STORAGE_DIR, "uploads")

os.makedirs(STORAGE_DIR,  exist_ok=True)
os.makedirs(REPORTS_DIR,  exist_ok=True)
os.makedirs(CHARTS_DIR,   exist_ok=True)
os.makedirs(UPLOADS_DIR,  exist_ok=True)

POSTGRES_HOST= os.getenv("POSTGRES_HOST")
POSTGRES_PORT=os.getenv("POSTGRES_PORT")
POSTGRES_DB=os.getenv("POSTGRES_DB")
POSTGRES_USER=os.getenv("POSTGRES_USER")
POSTGRES_PASSWORD=os.getenv("POSTGRES_PASSWORD")

# -- Auth -------------------------------------------------------------------
JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY", "change-this-secret-key")
JWT_ALGORITHM      = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))  # 24 hours
GOOGLE_CLIENT_ID   = os.getenv("GOOGLE_CLIENT_ID", "")