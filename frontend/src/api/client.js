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

  chat: (query, docId = null) =>
    http.post("/api/v1/chat", {
      query,
      doc_id: docId && docId !== "all" ? docId : null,
    }),

  compare: (docIds, query) =>
    http.post("/api/v1/compare", { query, doc_ids: docIds }),

  listDocuments: () => http.get("/api/v1/documents"),

  getDocument: (docId) => http.get(`/api/v1/documents/${docId}`),

  getDocumentSummary: (docId) =>
    http.get(`/api/v1/documents/${docId}/summary`),

  deleteDocument: (docId) => http.delete(`/api/v1/documents/${docId}`),

  clearMemory: () => http.delete("/api/v1/memory"),

  getHistory: (limit = 50) =>
    http.get("/api/v1/history", { params: { limit } }),

  clearHistory: () => http.delete("/api/v1/history"),

  scoreQuery: (n = 10) =>
    http.post("/api/v1/eval/score", { n }),

  getEvalResults: () => http.get("/api/v1/eval/results"),

  clearEvalResults: () => http.delete("/api/v1/eval/results"),
};

// ─── Data / BI  (v2) ────────────────────────────────────────────────────────

export const dataApi = {
  uploadFile: (file, onProgress) => {
    const fd = new FormData();
    fd.append("file", file);
    return http.post("/api/v2/upload", fd, {
      headers: { "Content-Type": "multipart/form-data" },
      onUploadProgress: (e) =>
        onProgress && onProgress(Math.round((e.loaded * 100) / e.total)),
    });
  },

  askQuestion: (fileId, question, sheetName) =>
    http.post("/api/v2/question", {
      file_id:    fileId,
      query:      question,
      sheet_name: sheetName || undefined,
    }),

  getColumnValues: (fileId) =>
    http.get(`/api/v2/columns/${fileId}`),

  getSummary: (fileId) => http.get(`/api/v2/summary/${fileId}`),

  getAnomalies: (fileId) => http.get(`/api/v2/anomalies/${fileId}`),

  generateChart: (fileId, chartType, xCol, yCol, title, aggregation, filterCol, filterValues, colorCol, sheetName) =>
    http.post("/api/v2/chart", {
      file_id:       fileId,
      chart_type:    chartType,
      x_col:         xCol,
      y_col:         yCol         || undefined,
      title:         title        || undefined,
      aggregation:   aggregation  || "count",
      filter_col:    filterCol    || undefined,
      filter_values: filterValues || [],
      color_col:     colorCol     || undefined,
      sheet_name:    sheetName    || undefined,
    }),

  getReport: (fileId) => http.get(`/api/v2/report/${fileId}`),

  downloadReport: (reportId) =>
    http.get(`/api/v2/download/report/${reportId}`, { responseType: "blob" }),

  listFiles: () => http.get("/api/v2/files"),

  getFile: (fileId) => http.get(`/api/v2/files/${fileId}`),

  deleteFile: (fileId) => http.delete(`/api/v2/files/${fileId}`),

  // offset param added for paginated infinite scroll
  getHistory: (fileId, limit = 10, offset = 0) =>
    http.get(`/api/v2/history/${fileId}`, { params: { limit, offset } }),

  getQueryLog: (limit = 100) =>
    http.get("/api/v2/query-log", { params: { limit } }),

  getQueryLogByFile: (fileId, limit = 100) =>
    http.get(`/api/v2/query-log/${fileId}`, { params: { limit } }),

  getQueryLogSummary: () =>
    http.get("/api/v2/query-log-summary"),

  clearQueryLog: () =>
    http.delete("/api/v2/query-log"),
};