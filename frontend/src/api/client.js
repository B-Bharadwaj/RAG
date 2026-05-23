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

  // Generates summary on first call, cached on subsequent
  getDocumentSummary: (docId) =>
    http.get(`/api/v1/documents/${docId}/summary`),

  deleteDocument: (docId) => http.delete(`/api/v1/documents/${docId}`),

  // Clears LLM memory only — does NOT affect history or eval
  clearMemory: () => http.delete("/api/v1/memory"),

  getHistory: (limit = 50) =>
    http.get("/api/v1/history", { params: { limit } }),

  clearHistory: () => http.delete("/api/v1/history"),

  // body: { n } — scores n most recent un-scored queries
  scoreQuery: (n = 10) =>
    http.post("/api/v1/eval/score", { n }),

  // returns { summary: { total, avg_faithfulness, avg_relevancy, avg_context_recall }, scores[] }
  getEvalResults: () => http.get("/api/v1/eval/results"),

  clearEvalResults: () => http.delete("/api/v1/eval/results"),
};

// ─── Data / BI  (v2) ────────────────────────────────────────────────────────

export const dataApi = {
  // POST /upload → { file_id, file_name, file_type, sheet_names[], shape, insights, anomaly_count }
  uploadFile: (file, onProgress) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/api/v2/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) =>
        onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
    });
  },

  // POST /question → { answer, follow_ups, sql, chart? }
  askQuestion: (fileId, question, sheetName) =>
    http.post("/api/v2/question", {
      file_id: fileId,
      query: question,
      sheet_name: sheetName || undefined,
    }),

  // GET /columns/{file_id} → { columns: [{ name, type, unique_values[], unique_count, min, max }] }
  getColumnValues: (fileId) =>
    http.get(`/api/v2/columns/${fileId}`),

  // GET /summary/{file_id} → { file_id, summary }
  getSummary: (fileId) => http.get(`/api/v2/summary/${fileId}`),

  // GET /anomalies/{file_id} → { file_id, anomalies[], explanation }
  getAnomalies: (fileId) => http.get(`/api/v2/anomalies/${fileId}`),

  // POST /chart → Chart.js compatible data { chart_id, title, chart_type, labels, values, datasets[] }
  generateChart: (fileId, chartType, xCol, yCol, title, aggregation, filterCol, filterValues, colorCol, sheetName) =>
    http.post("/api/v2/chart", {
      file_id: fileId,
      chart_type: chartType,
      x_col: xCol,
      y_col: yCol || undefined,
      title: title || undefined,
      aggregation: aggregation || "count",
      filter_col: filterCol || undefined,
      filter_values: filterValues || [],
      color_col: colorCol || undefined,
      sheet_name: sheetName || undefined,
    }),

  // GET /report/{file_id} → { report_id, file_id, file_path, timestamp }
  getReport: (fileId) => http.get(`/api/v2/report/${fileId}`),

  // GET /download/report/{report_id} → markdown blob
  downloadReport: (reportId) =>
    http.get(`/api/v2/download/report/${reportId}`, { responseType: "blob" }),

  listFiles: () => http.get("/api/v2/files"),

  getFile: (fileId) => http.get(`/api/v2/files/${fileId}`),

  deleteFile: (fileId) => http.delete(`/api/v2/files/${fileId}`),

  getHistory: (fileId, limit = 20) =>
    http.get(`/api/v2/history/${fileId}`, { params: { limit } }),

  // Query log endpoints
  getQueryLog: (limit = 100) =>
    http.get("/api/v2/query-log", { params: { limit } }),

  getQueryLogByFile: (fileId, limit = 100) =>
    http.get(`/api/v2/query-log/${fileId}`, { params: { limit } }),

  getQueryLogSummary: () =>
    http.get("/api/v2/query-log-summary"),

  clearQueryLog: () =>
    http.delete("/api/v2/query-log"),
};
