import axios from "axios";

const http = axios.create({
  baseURL: "",
  timeout: 120000,
});

http.interceptors.response.use(
  (res) => res,
  (err) => {
    const msg =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      "An unexpected error occurred";
    return Promise.reject(new Error(msg));
  }
);

// ─── PDF / RAG  (v1) ────────────────────────────────────────────────────────

export const pdfApi = {
  uploadDocument: (file, onProgress) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/api/v1/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) =>
        onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
    });
  },

  // body: { query, doc_id: string|null }
  chat: (query, docId = null) =>
    http.post("/api/v1/chat", {
      query,
      doc_id: docId && docId !== "all" ? docId : null,
    }),

  // body: { query, doc_ids: string[] }
  compare: (docIds, query) =>
    http.post("/api/v1/compare", { query, doc_ids: docIds }),

  listDocuments: () => http.get("/api/v1/documents"),

  getDocument: (docId) => http.get(`/api/v1/documents/${docId}`),

  deleteDocument: (docId) => http.delete(`/api/v1/documents/${docId}`),

  clearMemory: () => http.delete("/api/v1/memory"),

  getHistory: () => http.get("/api/v1/history"),

  // body: { n } — backend pulls n most recent un-scored queries from DB
  scoreQuery: (n = 10) =>
    http.post("/api/v1/eval/score", { n }),

  getEvalResults: () => http.get("/api/v1/eval/results"),

  clearEvalResults: () => http.delete("/api/v1/eval/results"),

  clearHistory: () => http.delete("/api/v1/history"),
};

// ─── Data / BI  (v2) ────────────────────────────────────────────────────────

export const dataApi = {
  // POST /upload — multipart, returns UploadResponse
  uploadFile: (file, onProgress) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/api/v2/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) =>
        onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
    });
  },

  // POST /question — body: { file_id, query, sheet_name? }
  askQuestion: (fileId, question, sheetName) =>
    http.post("/api/v2/question", {
      file_id:    fileId,
      query:      question,
      sheet_name: sheetName || undefined,
    }),

  // GET /summary/{file_id} → SummaryResponse { file_id, summary }
  getSummary: (fileId) => http.get(`/api/v2/summary/${fileId}`),

  // GET /anomalies/{file_id} → AnomalyResponse { file_id, anomalies[], explanation }
  getAnomalies: (fileId) => http.get(`/api/v2/anomalies/${fileId}`),

  // POST /chart — body: { file_id, chart_type, x_col, y_col, title?, color_col?, sheet_name? }
  generateChart: (fileId, chartType, xCol, yCol, title, colorCol, sheetName) =>
    http.post("/api/v2/chart", {
      file_id:    fileId,
      chart_type: chartType,
      x_col:      xCol,
      y_col:      yCol || undefined,
      title:      title || undefined,
      color_col:  colorCol || undefined,
      sheet_name: sheetName || undefined,
    }),

  // GET /report/{file_id} → ReportResponse { report_id, file_id, file_path, timestamp }
  getReport: (fileId) => http.get(`/api/v2/report/${fileId}`),

  // GET /download/report/{report_id} → file download
  downloadReport: (reportId) =>
    http.get(`/api/v2/download/report/${reportId}`, { responseType: "blob" }),

  // GET /files → FileInfoResponse[]
  listFiles: () => http.get("/api/v2/files"),

  // GET /files/{file_id} → FileInfoResponse
  getFile: (fileId) => http.get(`/api/v2/files/${fileId}`),

  // DELETE /files/{file_id}
  deleteFile: (fileId) => http.delete(`/api/v2/files/${fileId}`),


  // ─── Query Log (/api/v2/query-log) ──────────────────────────────────────────
  getQueryLog: () => http.get('/api/v2/query-log'),
  getQueryLogByFile: (fileId) => http.get(`/api/v2/query-log/${fileId}`),
  getQueryLogSummary: () => http.get('/api/v2/query-log-summary'),
  clearQueryLog: () => http.delete('/api/v2/query-log'),
  // GET /history/{file_id}?limit=20 → { file_id, history[] }
  getHistory: (fileId, limit = 20) =>
    http.get(`/api/v2/history/${fileId}`, { params: { limit } }),
};