# RAG+ — AI Business Intelligence Platform

> Built during GenAI Internship at Happiest Minds Technologies.
> LangChain-free. Built from scratch. Powered by Groq.

---

## Overview

RAG+ is a full-stack AI platform with two complete pipelines:

- **PDF Mode** — Deep question answering over research papers and documents
- **Data Mode** — Precise business intelligence over CSV and Excel files

Both pipelines are exposed through a FastAPI REST API and a React frontend.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         React Frontend                           │
│   PDF Mode:  Chat | Upload | Manage | Compare | Eval | Report    │
│   Data Mode: Upload | Chat | Visualize | Report | Query Log      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                FastAPI Backend (24 endpoints)                     │
│            /api/v1 — PDF RAG      /api/v2 — Data BI              │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
┌───────────────▼──────────┐   ┌─────────────▼────────────────────┐
│          SQLite           │   │           PostgreSQL              │
│  PDF registry             │   │  CSV/Excel data tables           │
│  Chat history             │   │  Business file registry          │
│  Eval scores              │   │  Analysis history                │
└──────────────────────────┘   │  SQL query log                   │
                                └──────────────────────────────────┘
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
| Databases | SQLite + PostgreSQL |
| Frontend | React + Chart.js |
| PDF Processing | PyMuPDF + pypdf |
| Data Processing | Pandas |

---

## PDF Mode

### Retrieval Pipeline

- Hybrid FAISS HNSW + BM25 Okapi retrieval running in parallel
- Per-document BM25 indices for scoped single-paper search
- Cross-encoder reranking — re-scores every candidate by reading full query and chunk together
- 3-variation LLM query expansion to improve recall
- MD5 exact-hash and cosine near-deduplication (threshold 0.95)
- Conversation memory scoped per-PDF or globally

### Document Processing

- Sentence-aware text chunking with configurable size and overlap
- Per-figure extraction using PyMuPDF — individual figure crops, not full pages
- Groq Vision (llama-4-scout) captioning for each extracted figure
- Figure captions stored as searchable chunks
- Auto metadata extraction — title, authors, abstract from first page

### Chat Features

- Ask across all PDFs simultaneously or scope to a single paper
- Multi-paper comparison across 2-3 papers with conflict detection
- Figures rendered inline when diagram queries are detected
- Source dropdown with page number and text preview per answer
- Follow-up question suggestions after every answer

### Evaluation Pipeline

- On-demand scoring using a judge LLM (llama-3.3-70b)
- Three metrics: Faithfulness, Answer Relevancy, Context Recall
- Evaluation tab fully independent from chat memory
- Failure analysis surfaces the dangerous RAG pattern: high faithfulness + low context recall

### PDF Report Tab

- On-demand paper summary generation with SQLite caching
- Zero tokens wasted — summaries only generated when user requests them
- Per-paper cards with title, authors, abstract, and summary
- Chat history export as CSV

---

## Data Mode

### Text-to-SQL Pipeline

```
User question
      ↓
LLM reads PostgreSQL schema
      ↓
LLM generates precise SQL query
      ↓
SQL runs on PostgreSQL → exact results
      ↓
LLM converts rows to natural language answer
      ↓
Chart generated if question is visual
```

Fallback to stats-based answer if SQL fails or returns NOT_SQL.

### SQL-Driven Analytics

- File summary: 5 analytical SQL queries run on upload → real insights with exact numbers
- Anomaly detection: 4 SQL queries detect nulls, duplicates, outliers, suspicious patterns
- Executive summary and full report generated entirely from SQL results
- No Pandas statistics sent to the LLM anywhere

### SQL Query Logging

Every query logged with: original question, generated SQL, execution status, rows returned, timestamp.
Full auditability — every answer traceable back to the exact SQL that produced it.

### Chart Generation Pipeline

```
Natural language question
      ↓
Specific value detection ("Bangalore vs Pune")
      ↓
LLM generates SQL with WHERE IN filter
      ↓
SQL runs on PostgreSQL → exact filtered data
      ↓
Chart.js compatible arrays returned to frontend
```

- Grouped bar charts for cross-tabulation (e.g. "Bachelors vs Masters by Gender")
- Manual chart builder with column value filter UI
- Aggregation options: Count, Sum, Average, Min, Max
- Supported chart types: bar, line, pie, histogram, scatter

---

## Project Structure

```
RAG_v3/
├── backend/
│   ├── pipeline/
│   │   ├── loader.py           — PDF + CSV/Excel loading
│   │   ├── chunker.py          — sentence-aware text chunking
│   │   ├── indexer.py          — FAISS + BM25 indexing
│   │   ├── retriever.py        — hybrid search + reranking
│   │   ├── ocr.py              — Groq Vision figure captioning
│   │   ├── processor.py        — lightweight file metadata
│   │   └── db.py               — SQLite operations (PDF mode)
│   ├── generation/
│   │   └── generator.py        — all LLM generation functions
│   ├── services/
│   │   ├── analyzer.py         — Data Mode orchestration
│   │   ├── chart_generator.py  — SQL-driven chart pipeline
│   │   ├── report_generator.py — SQL-driven report generation
│   │   ├── sql_engine.py       — PostgreSQL operations
│   │   └── query_logger.py     — query log wrapper
│   ├── routers/
│   │   ├── rag.py              — /api/v1 PDF endpoints
│   │   └── analyzer.py         — /api/v2 Data endpoints
│   ├── eval/
│   │   └── run_eval.py         — evaluation pipeline
│   ├── models/
│   │   └── schemas.py          — Pydantic request/response models
│   ├── prompts.py              — all LLM prompts
│   ├── config.py               — configuration
│   └── main.py                 — FastAPI app entry point
└── frontend/
    └── src/
        ├── pages/
        │   ├── pdf/            — PDF Mode tabs
        │   └── data/           — Data Mode tabs
        ├── components/
        │   ├── shared/         — TopNav, Sidebar, MarkdownContent
        │   └── data/           — ChartRenderer, FileSelector
        └── api/
            └── client.js       — all API calls
```

---

## API Reference

### PDF RAG — `/api/v1`

| Method | Endpoint | Description |
|---|---|---|
| POST | /upload | Upload and process a PDF |
| POST | /chat | Ask a question |
| POST | /compare | Compare 2-3 papers |
| GET | /documents | List all indexed documents |
| GET | /documents/{doc_id}/summary | On-demand summary with caching |
| DELETE | /documents/{doc_id} | Delete document |
| DELETE | /memory | Clear conversation memory |
| GET | /history | Recent chat history |
| DELETE | /history | Clear chat history |
| POST | /eval/score | Score recent queries |
| GET | /eval/results | Get eval scores and summary |
| DELETE | /eval/results | Clear eval scores |

### Business Intelligence — `/api/v2`

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
| GET | /files | List all uploaded files |
| GET | /files/{file_id} | Get file info |
| DELETE | /files/{file_id} | Delete file and PostgreSQL tables |
| GET | /history/{file_id} | Q&A history |
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
Groq API key
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

# Copy and fill environment variables
cp .env.example .env
# Add your GROQ_API_KEY to .env

# Start server
uvicorn main:app --reload
```

### PostgreSQL Setup

```sql
CREATE DATABASE ragbot;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE ragbot TO postgres;
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### API Documentation

```
Swagger UI → http://localhost:8000/docs
ReDoc      → http://localhost:8000/redoc
```

---

## Environment Variables

```env
GROQ_API_KEY=your_groq_api_key

# PostgreSQL
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ragbot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# Models
GROQ_MODEL_NAME=llama-3.1-8b-instant
GROQ_MODEL_LARGE=llama-3.3-70b-versatile
GROQ_MODEL_SMALL=llama-3.1-8b-instant

# Storage
UPLOADS_DIR=storage/uploads
CHARTS_DIR=storage/charts
REPORTS_DIR=storage/reports
```

---

## Key Design Decisions

**Why no LangChain?**
Built from scratch to understand every component — retrieval, reranking, generation, evaluation. Full control over the pipeline with no hidden abstractions.

**Why dual database?**
PDF mode needs fast key-value lookups — SQLite is perfect. Data mode needs SQL queries on structured tabular data — PostgreSQL is the right tool. Mixing them would create unnecessary coupling.

**Why Text-to-SQL instead of RAG for structured data?**
RAG on tabular data gives approximate answers from statistical summaries. SQL on the actual data gives exact answers. For business intelligence, precision matters.

**Why Chart.js over Plotly?**
Lighter bundle, simpler API, better React integration, and full control over styling. Plotly's JSON format is complex and hard to serialize cleanly through a REST API.

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

---

*Happiest Minds Technologies — GenAI Internship 2025*
