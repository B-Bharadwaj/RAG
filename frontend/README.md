# AI Business Report Analyzer — Frontend

Production-grade React frontend for the AI Business Report Analyzer, connecting to a FastAPI backend at `http://localhost:8000`.

---

## Quick Start

```bash
cd frontend
npm install
npm start
```

The app opens at `http://localhost:3000`. The `proxy` setting in `package.json` forwards all `/api/v1` and `/api/v2` calls to `http://localhost:8000`.

---

## Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── api/
│   │   └── client.js          — All API calls (pdfApi + dataApi)
│   ├── components/
│   │   ├── shared/
│   │   │   ├── TopNav.jsx     — Mode switcher nav bar
│   │   │   ├── Sidebar.jsx    — Per-mode navigation
│   │   │   ├── UploadZone.jsx — Drag-and-drop upload
│   │   │   ├── LoadingDots.jsx
│   │   │   └── MarkdownContent.jsx
│   │   └── data/
│   │       ├── ChartRenderer.jsx  — Recharts wrapper (bar/line/pie/scatter/hist)
│   │       └── FileSelector.jsx   — File dropdown for Data mode
│   ├── pages/
│   │   ├── pdf/
│   │   │   ├── PdfChat.jsx    — RAG chat + sources
│   │   │   ├── PdfUpload.jsx  — PDF upload + progress
│   │   │   ├── PdfManage.jsx  — Document table + delete
│   │   │   ├── PdfCompare.jsx — Multi-paper comparison
│   │   │   └── PdfEval.jsx    — Judge LLM evaluation dashboard
│   │   └── data/
│   │       ├── DataUpload.jsx    — CSV/Excel upload + KPI cards
│   │       ├── DataChat.jsx      — BI chat with inline charts
│   │       ├── DataVisualize.jsx — Chart builder + anomalies + AI insights
│   │       ├── DataReport.jsx    — Executive report + download
│   │       └── DataQueryLog.jsx  — Full Q&A + SQL history
│   ├── styles/
│   │   └── global.css         — Design system (CSS variables, components)
│   ├── App.jsx                — Router + layout shell
│   └── index.js
├── package.json
└── README.md
```

---

## Modes

### PDF Mode (`/api/v1`)
| Page | Route | Endpoint(s) |
|------|-------|-------------|
| Chat | `/pdf/chat` | `POST /chat`, `GET /history`, `DELETE /memory` |
| Upload | `/pdf/upload` | `POST /upload` |
| Manage | `/pdf/manage` | `GET /documents`, `DELETE /documents/:id` |
| Compare | `/pdf/compare` | `POST /compare`, `GET /documents` |
| Eval | `/pdf/eval` | `POST /eval/score`, `GET /eval/results`, `DELETE /eval/results` |

### Data Mode (`/api/v2`)
| Page | Route | Endpoint(s) |
|------|-------|-------------|
| Upload | `/data/upload` | `POST /upload`, `GET /files`, `DELETE /files/:id` |
| Chat | `/data/chat` | `POST /question`, `GET /history/:file_id` |
| Visualize | `/data/visualize` | `POST /chart`, `GET /anomalies/:id`, `GET /summary/:id` |
| Report | `/data/report` | `GET /report/:id`, `GET /download/report/:id` |
| Query Log | `/data/querylog` | `GET /history/:file_id` |

---

## Design System

The UI uses a custom CSS design system with no component libraries:

- **Dark theme** with `--bg-base: #0a0a0b` base and neutral gray scale
- **Typography**: Syne (headings) + DM Mono (code/data)
- **Colors**: Accent `#e0e0ff`, with semantic success/warning/danger/info
- **Components**: Cards, tables, chips, badges, upload zones, chat bubbles — all in `global.css`

---

## State Management

The active data file ID is stored in `App.jsx` and passed as props to all Data Mode pages. This ensures that switching between chat, visualize, report, and query log pages maintains the same active file context.

---

## API Client

All API calls are centralized in `src/api/client.js`:

```js
import { pdfApi, dataApi } from "./api/client";

// PDF
await pdfApi.chat("What is the main finding?", ["doc-id-1"]);
await pdfApi.uploadDocument(file, (pct) => console.log(pct));

// Data
await dataApi.askQuestion("file-id-123", "What is the average revenue?");
await dataApi.generateChart("file-id-123", "bar", "month", "revenue", "Monthly Revenue");
```

---

## Backend Requirements

The FastAPI backend must be running at `http://localhost:8000` with:
- CORS enabled for `http://localhost:3000`
- All endpoints listed above available

---

## Dependencies

- `react` 18 + `react-dom`
- `react-router-dom` v6
- `axios` for HTTP
- `recharts` for charts
- No UI component libraries — custom CSS only
