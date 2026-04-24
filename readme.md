# AI Business Report Analyzer — v2

---

## Table of Contents

- [Overview](#overview)
- [Two Specialized Pipelines](#two-specialized-pipelines)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the App](#running-the-app)
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [How It Works](#how-it-works)

---

## Overview

This project is a **v2 evolution** of a Multi-PDF RAG (Retrieval-Augmented Generation) system. While v1 focused on academic research papers, v2 extends the platform to handle structured business data alongside PDFs — making it useful for real business users, not just researchers.

The app has two modes accessible from a single unified interface:

- **📄 PDF Mode** — the complete v1 RAG pipeline for research papers and PDF documents
- **📊 Data Mode** — a new business intelligence pipeline for Excel and CSV files

Both pipelines are also exposed as a **unified REST API** — two complete AI systems under one FastAPI server, auto-documented via Swagger UI and ReDoc.

---

## Two Specialized Pipelines

v1 and v2 are not replacements of each other — they are purpose-built for different use cases. v1 remains the more technically sophisticated pipeline. v2 extends the platform's reach to structured business data.

### v1 — PDF RAG Pipeline (Research & Documents)
Built for deep, accurate question answering over unstructured document collections.

| Capability | Detail |
|---|---|
| Retrieval | Hybrid FAISS HNSW + BM25 Okapi with per-doc BM25 indices |
| Reranking | Cross-encoder (ms-marco-MiniLM-L-6-v2) for precision |
| Query expansion | 3 LLM-generated query variations to improve recall |
| Deduplication | MD5 exact-hash + cosine near-dedup (threshold 0.95) |
| Figure extraction | Per-figure cropping via PyMuPDF — not full-page OCR |
| Vision captioning | Groq Vision (llama-4-scout) for diagram understanding |
| Conversation memory | Scoped per-PDF or global across all documents |
| Paper comparison | Structured side-by-side analysis across 2-3 papers |
| Evaluation | Faithfulness + Answer Relevancy + Context Recall via judge LLM |
| Failure analysis | Surfaces low-scoring answers with retrieved chunks |
| REST API | 12 FastAPI endpoints under `/api/v1` |

### v2 — Data Intelligence Pipeline (Excel & CSV)
Built for business users who work with structured tabular data.

| Capability | Detail |
|---|---|
| File support | Excel (single + multi-sheet) and CSV |
| Statistical analysis | Min, max, mean, median, sum, std per numeric column |
| Anomaly detection | IQR outliers + negative values + high null rate detection |
| Auto chart generation | LLM picks chart type and columns from natural language |
| Chart types | Bar, line, pie, histogram, scatter via Plotly |
| Executive summary | AI-generated professional business summary |
| Report download | Full markdown report with stats, anomalies, insights |
| REST API | 12 FastAPI endpoints under `/api/v2` |
| Data privacy | Full dataset stays local — only statistical summary sent to LLM |

---

## Architecture

### PDF Mode (v1 RAG Pipeline)

```
User Query
    │
    ▼
Query Resolution (conversation history)
    │
    ▼
Query Expansion (3 variations via LLM)
    │
    ▼
Hybrid Retrieval
  ├── FAISS HNSW (dense semantic search)
  └── BM25 Okapi (sparse keyword search)
    │
    ▼
Cross-Encoder Reranking (ms-marco-MiniLM-L-6-v2)
    │
    ▼
Context Assembly + Token Budget Trimming
    │
    ▼
LLM Generation (llama-3.1-8b via Groq)
    │
    ▼
Answer + Sources + Figure Image (if diagram query)
    │
    ▼
Judge Evaluation (llama-3.3-70b — on demand)
  ├── Faithfulness
  ├── Answer Relevancy
  └── Context Recall → saved to SQLite
```

### Data Mode (v2 Pandas Pipeline)

```
User uploads Excel / CSV
    │
    ▼
File Loader (Pandas)
    │
    ▼
Processor
  ├── Statistical summary (min, max, mean, median, sum)
  ├── Categorical analysis (top values, unique counts)
  ├── Anomaly detection (IQR, nulls, negative values)
  └── Context compression (3000 char summary)
    │
    ▼
User asks a question
    │
    ▼
Chart detection (keyword matching + LLM column picker)
    │
    ├── Text answer ← Groq LLM (llama-3.3-70b)
    └── Auto chart  ← Plotly (rendered inline in chat)
    │
    ▼
Executive Summary / Report generation (on demand)
```

### Unified API Architecture

```
FastAPI Server (http://localhost:8000)
    │
    ├── /api/v1/...  ← PDF RAG Pipeline (routers/rag.py)
    │     ├── upload, chat, compare
    │     ├── documents CRUD
    │     ├── memory management
    │     └── eval scoring
    │
    ├── /api/v2/...  ← Business Intelligence (routers/analyzer.py)
    │     ├── upload, question, chart
    │     ├── summary, anomalies, report
    │     └── files CRUD
    │
    ├── /docs        ← Swagger UI (interactive testing)
    └── /redoc       ← ReDoc (shareable documentation)
```

---

## Project Structure

```
RAG_v2/
│
├── pipeline/
│   ├── loader.py          # PDF + Excel + CSV file loading
│   ├── chunker.py         # Sentence-aware text chunking
│   ├── indexer.py         # FAISS HNSW + BM25 indexing
│   ├── retriever.py       # Hybrid retrieval + reranking
│   ├── processor.py       # Pandas statistical analysis
│   ├── ocr.py             # Groq Vision figure extraction
│   └── db.py              # SQLite registry (docs, history, eval, business files)
│
├── generation/
│   └── generator.py       # LLM generation (v1 RAG + v2 business Q&A)
│
├── eval/
│   ├── judge.py           # Judge LLM scoring agent
│   ├── run_eval.py        # Batch evaluation runner
│   └── test_generator.py  # Auto Q&A pair generation
│
├── services/
│   ├── analyzer.py        # Orchestrates v2 pipeline (upload → process → answer)
│   ├── chart_generator.py # Plotly chart generation + auto column picking
│   └── report_generator.py# Markdown executive report builder
│
├── routers/
│   ├── rag.py             # v1 PDF RAG API endpoints (/api/v1)
│   └── analyzer.py        # v2 Business Intelligence endpoints (/api/v2)
│
├── models/
│   └── schemas.py         # Pydantic request/response models
│
├── storage/               # Auto-created at runtime
│   ├── index.faiss        # FAISS vector index
│   ├── metadata.pkl       # Chunk metadata
│   ├── bm25.pkl           # Global + per-doc BM25 indices
│   ├── registry.db        # SQLite database
│   ├── uploads/           # Saved uploaded business files
│   ├── charts/            # Generated Plotly HTML charts
│   ├── reports/           # Generated markdown reports
│   └── images/            # Extracted PDF figure PNGs
│
├── streamlit_app.py       # Main UI — dual mode (PDF + Data)
├── main.py                # FastAPI entry point — both pipelines
├── prompts.py             # All LLM prompts in one place
├── config.py              # All configuration from .env
├── styles.py              # Dark theme CSS
├── .env                   # API keys (not committed)
└── requirements.txt       # Python dependencies
```

---

## Tech Stack

| Component | Tool | Purpose |
|---|---|---|
| Language | Python 3.10+ | Core language |
| LLM (generation) | Llama 3.1 8B via Groq | Fast Q&A generation |
| LLM (complex tasks) | Llama 3.3 70B via Groq | Insights, anomaly explanation, judge |
| Vision model | Llama 4 Scout via Groq | PDF figure captioning |
| Embeddings | all-MiniLM-L6-v2 | Sentence embeddings for FAISS |
| Reranker | ms-marco-MiniLM-L-6-v2 | Cross-encoder reranking |
| Vector search | FAISS HNSW | Dense semantic retrieval |
| Keyword search | BM25 Okapi | Sparse keyword retrieval |
| Data analysis | Pandas + NumPy | Tabular data processing |
| Charts | Plotly | Interactive visualizations |
| PDF parsing | PyMuPDF + pypdf | Text extraction + image rendering |
| Database | SQLite | Document registry + eval scores |
| API | FastAPI + Pydantic | REST endpoints + validation |
| API docs | Swagger UI + ReDoc | Auto-generated interactive documentation |
| Frontend | Streamlit | Web UI |
| Config | python-dotenv | Environment variable management |

---

## Installation

### Prerequisites

- Python 3.10+
- A Groq API key (free tier works for POC)

### Steps

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd RAG_v2

# 2. Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

---

## Configuration

Create a `.env` file at the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
MAX_FILE_SIZE_MB=50
MAX_PAGE_COUNT=100
MAX_REQUESTS_PER_MINUTE=20
```

All other settings live in `config.py`:

| Variable | Default | Description |
|---|---|---|
| `GROQ_MODEL_NAME` | llama-3.1-8b-instant | Generation model |
| `GROQ_MODEL_LARGE` | llama-3.3-70b-versatile | Complex tasks model |
| `EMBED_MODEL_NAME` | all-MiniLM-L6-v2 | Embedding model |
| `RERANKER_MODEL_NAME` | ms-marco-MiniLM-L-6-v2 | Reranker model |
| `CHUNK_SIZE` | 800 | Max chars per text chunk |
| `CHUNK_OVERLAP` | 200 | Overlap between chunks |
| `TOP_K` | 5 | Chunks returned per retriever |
| `MAX_SAMPLE_ROWS` | 5 | Sample rows sent to LLM |
| `MAX_CONTEXT_CHARS` | 3000 | Max context chars per request |
| `MAX_HISTORY_TURNS` | 4 | Chat turns kept in memory |

---

## Running the App

### Option 1 — Streamlit UI (recommended for demo)

```bash
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501`

### Option 2 — FastAPI Backend Only

```bash
uvicorn main:app --reload
```

API documentation:
- **Swagger UI** (interactive testing): `http://localhost:8000/docs`
- **ReDoc** (shareable documentation): `http://localhost:8000/redoc`

### Option 3 — Run Both Together

Open two terminals:

```bash
# Terminal 1 — FastAPI
uvicorn main:app --reload

# Terminal 2 — Streamlit
streamlit run streamlit_app.py
```

---

## Features

### PDF Mode (v1 RAG Pipeline)

**Chat**
- Ask questions across all uploaded PDFs simultaneously
- Scope queries to a specific paper
- Sources shown with every answer (page number + text preview)
- Figures and diagrams rendered inline in chat
- Conversation memory with last 4 turns

**Upload**
- Multi-file PDF upload
- Automatic text extraction, chunking, and indexing
- Groq Vision figure captioning (per-figure, not full page)
- Auto metadata extraction (title, authors, abstract)
- Auto 3-paragraph paper summary generation
- Terminal-style progress log during processing

**Manage**
- View all indexed papers with metadata
- Search and filter by title, abstract, or summary
- Per-row delete with automatic index cleanup
- Paper details with abstract and auto-generated summary

**Compare**
- Side-by-side comparison of 2-3 papers
- Structured per-paper answer blocks
- Conflict detection between papers

**Eval**
- On-demand scoring of recent chat queries
- Three metrics: Faithfulness, Answer Relevancy, Context Recall
- Judge LLM: llama-3.3-70b (stronger than generation model)
- Score history table and failure analysis dashboard
- Surfaces the dangerous pattern: high faithfulness + low context recall

### Data Mode (v2 Pandas Pipeline)

**Upload**
- Excel (.xlsx, .xls) and CSV (.csv) support
- Multi-sheet Excel handling
- Automatic statistical analysis on upload
- Auto-generated AI insights (5 key business observations)
- KPI cards: rows, columns, anomalies, sheets
- File persistence — survives Streamlit reruns

**Chat**
- Natural language Q&A about your data
- Conversational memory (last 4 turns)
- Auto chart detection — visual questions trigger chart generation
- Charts rendered inline below the text answer
- Follow-up question suggestions after each answer
- Example question chips for quick start

**Visualize**
- Manual chart builder — pick type, X axis, Y axis
- Chart types: bar, line, pie, histogram, scatter
- Auto title generation
- AI insights panel (generated at upload time)
- Anomaly detection panel with severity badges
- AI anomaly explanation in plain business English

**Report**
- Executive summary generation (professional, manager-ready)
- Full downloadable markdown report including:
  - Dataset overview
  - Numeric statistics table
  - Categorical statistics
  - Anomaly list with severity
  - AI generated insights
  - Executive summary
- Report preview in UI before download

---

## API Endpoints

Both pipelines are exposed under one FastAPI server.
Full interactive docs: `http://localhost:8000/docs`
Shareable docs: `http://localhost:8000/redoc`

### 📄 PDF RAG Pipeline — `/api/v1`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/health` | Health check + docs indexed count |
| POST | `/api/v1/upload` | Upload + process a PDF (text, OCR, index) |
| POST | `/api/v1/chat` | Ask a question (all PDFs or specific doc) |
| POST | `/api/v1/compare` | Compare 2-3 papers side by side |
| GET | `/api/v1/documents` | List all indexed documents |
| GET | `/api/v1/documents/{doc_id}` | Get document info, abstract, summary |
| DELETE | `/api/v1/documents/{doc_id}` | Delete document + index + images |
| DELETE | `/api/v1/memory` | Clear conversation memory |
| GET | `/api/v1/history` | Get recent chat history |
| POST | `/api/v1/eval/score` | Score recent queries with judge LLM |
| GET | `/api/v1/eval/results` | Get eval scores + summary statistics |
| DELETE | `/api/v1/eval/results` | Clear all eval scores |

### 📊 Business Intelligence Pipeline — `/api/v2`

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v2/health` | Health check |
| POST | `/api/v2/upload` | Upload + process Excel or CSV |
| POST | `/api/v2/question` | Ask a question about a file |
| GET | `/api/v2/summary/{file_id}` | Generate executive summary |
| GET | `/api/v2/anomalies/{file_id}` | Get anomalies with AI explanation |
| POST | `/api/v2/chart` | Generate a specific chart |
| GET | `/api/v2/report/{file_id}` | Build full markdown report |
| GET | `/api/v2/download/report/{id}` | Download report file |
| GET | `/api/v2/files` | List all uploaded files |
| GET | `/api/v2/files/{file_id}` | Get file info |
| DELETE | `/api/v2/files/{file_id}` | Delete file + data |
| GET | `/api/v2/history/{file_id}` | Get Q&A history for a file |

### Example Requests

**Upload a PDF:**
```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@research_paper.pdf"
```

**Ask a question about a PDF:**
```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the main contribution of this paper?",
    "doc_id": null
  }'
```

**Compare two papers:**
```bash
curl -X POST http://localhost:8000/api/v1/compare \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do the methods differ?",
    "doc_ids": ["doc-id-1", "doc-id-2"]
  }'
```

**Upload a CSV:**
```bash
curl -X POST http://localhost:8000/api/v2/upload \
  -F "file=@sales_data.csv"
```

**Ask a question about a CSV:**
```bash
curl -X POST http://localhost:8000/api/v2/question \
  -H "Content-Type: application/json" \
  -d '{
    "file_id": "your-file-id-here",
    "query": "Which country has the highest sales?"
  }'
```

---
## How It Works

### Retrieval — PDF Mode

When a user asks a question in PDF mode the system does not simply search for keywords. It runs the query through three stages:

1. **Query expansion** — generates 3 variations of the question via LLM to improve recall
2. **Hybrid retrieval** — FAISS HNSW (dense semantic search) + BM25 Okapi (sparse keyword search) run in parallel
3. **Cross-encoder reranking** — all candidates re-scored by ms-marco-MiniLM-L-6-v2 and sorted by relevance

This three-stage pipeline is significantly more accurate than single-vector search alone — the cross-encoder sees the full query and chunk together, not just their embeddings.

---

### Context Compression — Data Mode

When a user uploads a CSV or Excel file, the full dataset never leaves the machine. Instead the system builds a compressed statistical summary locally:

```
541,909 rows × 8 columns  (stays on your machine)
        ↓
Statistical summary ~3000 chars  (sent to Groq)
        ↓
Answer + optional chart returned
```

This is both a **privacy feature** and a **token efficiency feature** — sensitive business data is never exposed to an external API, and token usage stays well within free tier limits.

---

### Figure Extraction — PDF Mode

Most RAG systems send entire PDF pages to a vision model. This system extracts individual figures instead:

1. PyMuPDF detects figure bounding boxes using `get_images()` and `get_drawings()`
2. Each figure is cropped precisely — surrounding text is excluded
3. Each crop is sent to Groq Vision (llama-4-scout) for detailed captioning
4. Captions are stored as searchable chunks alongside text chunks
5. When a diagram query is detected, figure chunks are force-included in retrieval

This means figure captions are more accurate and the UI renders the exact figure PNG alongside the answer — not a full page screenshot.

---

### Auto Chart Detection — Data Mode

When a user asks a visual question, the system:

1. Detects chart intent from keywords (`trend`, `compare`, `distribution`, `by country`, etc.)
2. Sends column names + question to the LLM
3. LLM returns chart type + best columns as structured JSON
4. Plotly generates the chart and renders it inline in the chat below the text answer

The manual chart builder in the Visualize tab is always available as a fallback where the user has full control over column selection.

---

### Anomaly Detection — Data Mode

Three types of anomalies are detected automatically on every file upload:

- **Outliers** — IQR method (values beyond 1.5 × IQR from Q1/Q3)
- **Negative values** — flagged in columns that should never be negative (price, revenue, quantity)
- **High null rates** — columns with more than 20% missing values

Each anomaly is assigned a severity (high, medium, low) and the user can request a plain English AI explanation of what each anomaly means for their business.

---

### Evaluation Pipeline — PDF Mode

Every chat response in PDF mode can be scored on demand using a judge LLM:

- **Faithfulness** — are all claims in the answer grounded in the retrieved chunks?
- **Answer Relevancy** — does the answer directly address the question?
- **Context Recall** — did the retrieved chunks contain enough information to answer?

The judge uses llama-3.3-70b — a stronger model than the 8B generation model — because evaluation quality depends on reasoning ability. Scores are saved to SQLite and the failure analysis dashboard surfaces the most dangerous RAG pattern: high faithfulness combined with low context recall, meaning the model gave a confident answer from completely irrelevant chunks.

---

### Smart Model Routing — Both Pipelines

Both pipelines route tasks to the right model based on complexity, keeping usage within Groq's free tier limits:

```
PDF generation       → llama-3.1-8b-instant    (fast, 500k tokens/day)
PDF judge scoring    → llama-3.3-70b-versatile  (accurate, 100k tokens/day)
Data Q&A             → llama-3.3-70b-versatile  (complex reasoning needed)
Data summaries       → llama-3.1-8b-instant     (simple, saves tokens)
Chart column picking → llama-3.1-8b-instant     (fast + cheap)
```

---

### API Documentation — Both Pipelines

Both pipelines are exposed as a unified REST API. FastAPI auto-generates two documentation views directly from the code — no separate documentation work needed:

- **Swagger UI** (`/docs`) — interactive, lets you test every endpoint live from the browser
- **ReDoc** (`/redoc`) — clean three-panel layout, best for reading and sharing with team members or managers

---

## Evaluation Commands (PDF Mode)

```bash
# Generate test Q&A pairs from indexed PDFs
python -m eval.test_generator

# Run evaluation against the test set
python -m eval.run_eval --mode testset

# Run evaluation against recent live chat queries
python -m eval.run_eval --mode live --n 10
```

---

## Built During

**Internship Project — GenAI Intern**
Happiest Minds Technologies

**v1** — Multi-PDF RAG system for academic research papers

**v2** — Extended to full business intelligence platform with unified REST API

---

*Built with Groq, LangChain-free, from scratch.*