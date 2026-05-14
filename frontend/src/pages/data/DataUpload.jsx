import { useState } from "react";
import { dataApi } from "../../api/client";
import UploadZone from "../../components/shared/UploadZone";

export default function DataUpload({ onFileSelect }) {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (f) => {
    setFile(f);
    setStatus(null);
    setResult(null);
    setError("");
    setProgress(0);
  };

  const upload = async () => {
    if (!file) return;
    setStatus("uploading");
    setError("");
    try {
      const res = await dataApi.uploadFile(file, setProgress);
      setResult(res.data);
      setStatus("done");
      if (onFileSelect) onFileSelect(res.data?.file_id);
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  };

  // Backend UploadResponse fields:
  // file_id, file_name, file_type, status, sheet_names,
  // shape: { rows, cols }, insights, anomaly_count

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Upload Data File</h1>
            <p>Ingest Excel or CSV files for business intelligence analysis</p>
          </div>
        </div>

        <UploadZone
          accept=".csv,.xlsx,.xls"
          onFile={handleFile}
          label="Drop Excel or CSV file here"
          hint=".csv, .xlsx, .xls supported"
        />

        {file && (
          <div className="card mt-16">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 3 }}>{file.name}</div>
                <div className="text-sm text-muted">
                  {(file.size / 1024).toFixed(1)} KB &middot;{" "}
                  {file.name.endsWith(".csv") ? "CSV" : "Excel"}
                </div>
              </div>
              <button
                className="btn btn-primary"
                onClick={upload}
                disabled={status === "uploading" || status === "done"}
              >
                {status === "uploading" ? (
                  <><span className="spinner" /> Uploading…</>
                ) : status === "done" ? "Uploaded" : "Upload & Analyze"}
              </button>
            </div>
            {status === "uploading" && (
              <div className="progress-bar mt-12">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        )}

        {error && <div className="error-banner mt-16">{error}</div>}

        {status === "done" && result && (
          <>
            <div className="success-banner mt-16 mb-16">
              File processed successfully.
              <span className="text-mono" style={{ marginLeft: 8 }}>ID: {result.file_id}</span>
            </div>

            {/* KPI cards — uses shape.rows / shape.cols from backend */}
            <div className="kpi-grid">
              {result.shape?.rows != null && (
                <div className="kpi-card">
                  <div className="kpi-label">Rows</div>
                  <div className="kpi-value">{result.shape.rows.toLocaleString()}</div>
                </div>
              )}
              {result.shape?.cols != null && (
                <div className="kpi-card">
                  <div className="kpi-label">Columns</div>
                  <div className="kpi-value">{result.shape.cols}</div>
                </div>
              )}
              {result.anomaly_count != null && (
                <div className="kpi-card">
                  <div className="kpi-label">Anomalies</div>
                  <div className="kpi-value">{result.anomaly_count}</div>
                </div>
              )}
              {result.file_type && (
                <div className="kpi-card">
                  <div className="kpi-label">File Type</div>
                  <div className="kpi-value" style={{ fontSize: 16 }}>{result.file_type.toUpperCase()}</div>
                </div>
              )}
            </div>

            {/* Sheet names if Excel */}
            {result.sheet_names?.length > 0 && (
              <div className="card mt-16">
                <div className="card-title">Sheets Detected</div>
                <div className="chip-list">
                  {result.sheet_names.map((s) => (
                    <span key={s} className="chip selected" style={{ cursor: "default" }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {/* AI Insights */}
            {result.insights && (
              <div className="card mt-16">
                <div className="card-title">AI Insights</div>
                <p style={{ fontSize: 13.5, lineHeight: 1.75 }}>{result.insights}</p>
              </div>
            )}
          </>
        )}

        <div className="card mt-24">
          <div className="card-title">How it works</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginTop: 8 }}>
            {[
              "Upload a CSV or Excel file — the system parses columns, detects data types, and computes statistics automatically",
              "Ask questions in plain English — the AI generates SQL or pandas queries behind the scenes and returns a direct answer",
              "Visualize trends, detect anomalies, and download a full executive report with one click"
            ].map((step, i) => (
              <div key={i} style={{ display: "flex", gap: 12 }}>
                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 8px", height: "fit-content", color: "var(--text-muted)", flexShrink: 0 }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <p style={{ fontSize: 13 }}>{step}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
