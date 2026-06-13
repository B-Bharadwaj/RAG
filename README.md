# RAGBot — AI Business Intelligence Platform

> Built during GenAI Internship at Happiest Minds Technologies.
> LangChain-free. Built from scratch. Powered by Groq.
> **Live Demo:** [bharadwaj-ragbot.vercel.app](https://bharadwaj-ragbot.vercel.app)
---

## Overview

RAGBot is a full-stack AI platform with two complete pipelines and JWT-based user authentication:

- **PDF Mode** — Deep question answering over research papers and documents
- **Data Mode** — Precise business intelligence over CSV and Excel files using Text-to-SQL

Both pipelines are exposed through a FastAPI REST API and a React frontend with per-user data isolation.

---

## System Architecture

```
+---------------------------------------------------------------------+
|                         React Frontend                              |
|  Auth: Login | Register | Google OAuth                              |
|  PDF Mode:  Chat | Upload | Manage | Compare | Eval | Report        |
|  Data Mode: Upload | Chat | Visualize | Report | Query Log          |
+----------------------------+----------------------------------------+
                             |  JWT Token (Bearer)
+----------------------------v----------------------------------------+
|                   FastAPI Backend (27 endpoints)                    |
|   /api/auth -- Authentication    /api/v1 -- PDF RAG                 |
|                                  /api/v2 -- Data BI                 |
|                 JWT Middleware (all routes protected)               |
+----------+------------------------------------+---------------------+
           |                                    |
+----------v---------+            +-------------v-------------------+
|       SQLite       |            |          PostgreSQL             |
|  PDF registry      |            |  users table                   |
|  Chat history      |            |  business_files (per user)     |
|  Eval scores       |            |  analysis_history (per user)   |
+--------------------+            |  query_log (per user)          |
                                  |  CSV/Excel data tables         |
                                  +--------------------------------+
                                             |
                                  +----------v----------+
                                  |    Groq LLM API     |
                                  |  llama-3.3-70b      |
                                  |  llama-3.1-8b       |
                                  |  llama-4-scout      |
                                  +---------------------+
```

---

## PDF Mode Architecture

```
PDF Upload
    |
    +-- PyMuPDF text extraction (per page)
    +-- Sentence-aware chunking (800 chars, 200 overlap)
    +-- Per-figure extraction -> Groq Vision captioning
    +-- MD5 dedup + cosine near-dedup (threshold 0.95)
    +-- FAISS HNSW indexing (all chunks)
    +-- BM25 indexing (per document)
    +-- Metadata extraction (title, authors, abstract)

User Question
    |
    +-- Standalone query resolution (via chat history)
    +-- 3-variation LLM query expansion
    +-- Hybrid search: FAISS HNSW + BM25 (parallel)
    +-- Per-PDF search for multi-paper coverage
    +-- Image chunk boosting (when diagram queries detected)
    +-- Cross-encoder reranking (ms-marco-MiniLM-L-6-v2)
    +-- Token budget trimming (3500 tokens max)
    +-- Groq generation with scoped memory
```

---

## Data Mode Architecture

```
CSV/Excel Upload
    |
    +-- Pandas loading (all sheets)
    +-- Load to PostgreSQL (pandas.to_sql)
    +-- 5 SQL queries -> LLM generates business summary
    +-- Register in business_files table (with user_id)

User Question
    |
    +-- LLM reads PostgreSQL schema
    +-- LLM generates precise SQL query
    +-- SQL executes on PostgreSQL -> exact rows
    +-- LLM converts rows to natural language answer
    +-- Specific value detection ("Bangalore vs Pune")
    +-- Chart SQL generated with WHERE IN filter
    +-- Chart.js arrays returned to frontend
    +-- Full chart data saved to analysis_history
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq (llama-3.3-70b, llama-3.1-8b, llama-4-scout) |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Reranker | cross-encoder (ms-marco-MiniLM-L-6-v2) |
| Vector Store | FAISS HNSW |
| Keyword Search | BM25 Okapi |
| Backend | FastAPI + Pydantic |
| Authentication | JWT (python-jose) + bcrypt + Google OAuth |
| Databases | SQLite (PDF mode) + PostgreSQL (Data mode) |
| Frontend | React + Chart.js |
| PDF Processing | PyMuPDF + pypdf |
| Data Processing | Pandas + SQLAlchemy |
| Deployment | Hugging Face Spaces + Vercel + Supabase |

---

## Project Structure

```
RAGBot/
+-- backend/
|   +-- pipeline/
|   |   +-- loader.py           -- PDF + CSV/Excel loading
|   |   +-- chunker.py          -- sentence-aware text chunking
|   |   +-- indexer.py          -- FAISS + BM25 indexing
|   |   +-- retriever.py        -- hybrid search + reranking
|   |   +-- ocr.py              -- Groq Vision figure captioning
|   |   +-- processor.py        -- lightweight file metadata
|   |   +-- db.py               -- SQLite operations (PDF mode)
|   +-- generation/
|   |   +-- generator.py        -- all LLM generation functions
|   +-- services/
|   |   +-- analyzer.py         -- Data Mode orchestration
|   |   +-- auth_service.py     -- JWT creation + password hashing
|   |   +-- chart_generator.py  -- SQL-driven chart pipeline
|   |   +-- report_generator.py -- SQL-driven report generation
|   |   +-- sql_engine.py       -- PostgreSQL operations
|   |   +-- query_logger.py     -- query log wrapper
|   +-- middleware/
|   |   +-- auth_middleware.py  -- JWT verification dependency
|   +-- routers/
|   |   +-- auth.py             -- /api/auth endpoints
|   |   +-- rag.py              -- /api/v1 PDF endpoints
|   |   +-- analyzer.py         -- /api/v2 Data endpoints
|   |   +-- sql.py              -- /api/v2 Query Log endpoints
|   +-- eval/
|   |   +-- run_eval.py         -- evaluation pipeline
|   +-- models/
|   |   +-- schemas.py          -- Pydantic request/response models
|   +-- config.py               -- configuration + env vars
|   +-- main.py                 -- FastAPI app entry point
+-- frontend/
    +-- src/
        +-- pages/
        |   +-- auth/           -- Login, Register
        |   +-- pdf/            -- Chat, Upload, Manage, Compare, Eval, Report
        |   +-- data/           -- Upload, Chat, Visualize, Report, QueryLog
        +-- components/
        |   +-- auth/           -- ProtectedRoute, GoogleButton
        |   +-- shared/         -- TopNav, Sidebar, MarkdownContent
        |   +-- data/           -- ChartRenderer, FileSelector
        +-- context/
        |   +-- AuthContext.jsx -- global auth state
        +-- api/
            +-- client.js       -- axios instance with JWT interceptor
```

---

## API Reference

### Authentication -- `/api/auth`

| Method | Endpoint | Description |
|---|---|---|
| POST | /register | Register with email + password |
| POST | /login | Login -> returns JWT token |
| POST | /google | Google OAuth -> returns JWT token |
| GET | /me | Get current user info |

### PDF RAG -- `/api/v1` *(JWT required)*

| Method | Endpoint | Description |
|---|---|---|
| POST | /upload | Upload and process a PDF |
| POST | /chat | Ask a question |
| POST | /compare | Compare 2-3 papers |
| GET | /documents | List all indexed documents |
| GET | /documents/{doc_id} | Get document info |
| GET | /documents/{doc_id}/summary | On-demand summary with caching |
| DELETE | /documents/{doc_id} | Delete document |
| DELETE | /memory | Clear conversation memory |
| GET | /history | Recent chat history |
| DELETE | /history | Clear chat history |
| POST | /eval/score | Score recent queries |
| GET | /eval/results | Get eval scores and summary |
| DELETE | /eval/results | Clear eval scores |

### Business Intelligence -- `/api/v2` *(JWT required)*

| Method | Endpoint | Description |
|---|---|---|
| POST | /upload | Upload CSV/Excel, load to PostgreSQL |
| POST | /question | Text-to-SQL answer + chart |
| GET | /columns/{file_id} | Column metadata and unique values |
| POST | /chart | SQL-driven manual chart with filtering |
| GET | /summary/{file_id} | SQL-driven executive summary |
| GET | /anomalies/{file_id} | SQL-driven anomaly detection |
| GET | /report/{file_id} | Generate full SQL-driven report |
| GET | /download/report/{report_id} | Download report as markdown |
| GET | /files | List user's uploaded files |
| GET | /files/{file_id} | Get file info |
| DELETE | /files/{file_id} | Delete file and PostgreSQL tables |
| GET | /history/{file_id} | Q&A history with chart data |
| GET | /query-log | All SQL query logs |
| GET | /query-log-summary | Aggregate query statistics |
| DELETE | /query-log | Clear all logs |

---

## Setup

### Prerequisites

```
Python 3.11+
Node.js 18+
PostgreSQL 14+
Groq API key (https://console.groq.com)
Google OAuth Client ID (optional)
```

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
pip install -r requirements.txt

# Create storage directories
mkdir -p storage/uploads storage/charts storage/reports storage/images
```

### PostgreSQL Setup

```sql
CREATE DATABASE ragbot;
```

### Environment Variables

```env
GROQ_API_KEY=your_groq_api_key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ragbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

# JWT Auth
JWT_SECRET_KEY=your-random-secret-key-here
JWT_EXPIRE_MINUTES=1440

# Google OAuth (optional)
GOOGLE_CLIENT_ID=your-google-client-id
```

### Start Backend

```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm start
```

### Frontend Environment Variables

```env
REACT_APP_API_URL=http://localhost:8000
REACT_APP_GOOGLE_CLIENT_ID=your-google-client-id
```

### API Documentation

```
Swagger UI -> http://localhost:8000/docs
ReDoc      -> http://localhost:8000/redoc
```

---

## Key Design Decisions

**Why no LangChain?**
Built from scratch to understand every component — retrieval, reranking, generation, evaluation. Full control over the pipeline with no hidden abstractions.

**Why dual database?**
PDF mode needs fast key-value lookups — SQLite is perfect. Data mode needs SQL queries on structured tabular data — PostgreSQL is the right tool.

**Why Text-to-SQL instead of RAG for structured data?**
RAG on tabular data gives approximate answers from statistical summaries. SQL on the actual data gives exact answers. For business intelligence, precision matters.

**Why JWT over session-based auth?**
Stateless — works perfectly with Hugging Face Spaces which can restart at any time. No server-side session storage needed.

**Why Chart.js over Plotly?**
Lighter bundle, simpler API, better React integration, and full control over styling. Plotly JSON is complex to serialize cleanly through a REST API.

---

## Built With

- [Groq](https://groq.com) — LLM inference
- [FAISS](https://github.com/facebookresearch/faiss) — vector similarity search
- [sentence-transformers](https://www.sbert.net) — embeddings and reranking
- [FastAPI](https://fastapi.tiangolo.com) — REST API
- [React](https://react.dev) — frontend
- [Chart.js](https://www.chartjs.org) — charts
- [PostgreSQL](https://www.postgresql.org) — structured data
- [PyMuPDF](https://pymupdf.readthedocs.io) — PDF processing
- [Supabase](https://supabase.com) — cloud PostgreSQL
- [Hugging Face Spaces](https://huggingface.co/spaces) — backend deployment
- [Vercel](https://vercel.com) — frontend deployment

---

*Happiest Minds Technologies — GenAI Internship 2026*
