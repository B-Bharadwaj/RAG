import { useState, useEffect } from "react";
import { dataApi } from "../../api/client";
import MarkdownContent from "../../components/shared/MarkdownContent";
import FileSelector from "../../components/data/FileSelector";

export default function DataReport({ activeFileId, onFileSelect }) {
  const [fileId, setFileId] = useState(activeFileId || "");
  const [report, setReport] = useState(null);       // { report_id, file_id, file_path, timestamp }
  const [content, setContent] = useState("");        // actual markdown text
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (activeFileId) setFileId(activeFileId);
  }, [activeFileId]);

  const handleSelectFile = (id) => {
    setFileId(id);
    setReport(null);
    setContent("");
    setError("");
    if (onFileSelect) onFileSelect(id);
  };

  const generateReport = async () => {
    if (!fileId) return;
    setLoading(true);
    setError("");
    setReport(null);
    setContent("");
    try {
      // Step 1: generate the report — returns { report_id, file_id, file_path, timestamp }
      const res = await dataApi.getReport(fileId);
      const reportMeta = res.data;
      setReport(reportMeta);

      // Step 2: fetch the actual markdown content using the download endpoint
      const dlRes = await dataApi.downloadReport(reportMeta.report_id);
      const text = await dlRes.data.text();   // blob → string
      setContent(text);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    if (!report?.report_id) return;
    setDownloading(true);
    try {
      const res = await dataApi.downloadReport(report.report_id);
      const blob = new Blob([res.data], { type: "text/markdown" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report_${report.report_id}.md`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError("Download failed: " + e.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Executive Report</h1>
            <p>AI-generated business intelligence report for your dataset</p>
          </div>
          <div className="page-header-actions">
            <FileSelector selectedId={fileId} onSelect={handleSelectFile} />
            {content && (
              <button
                className="btn btn-secondary"
                onClick={downloadReport}
                disabled={downloading}
              >
                {downloading ? <><span className="spinner" /> Downloading…</> : "Download Report"}
              </button>
            )}
            <button
              className="btn btn-primary"
              onClick={generateReport}
              disabled={loading || !fileId}
            >
              {loading ? <><span className="spinner" /> Generating…</> : "Generate Report"}
            </button>
          </div>
        </div>

        {error && <div className="error-banner mb-16">{error}</div>}

        {!fileId && (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Select a file to generate an executive report.</p>
          </div>
        )}

        {fileId && !report && !loading && (
          <div className="card" style={{ textAlign: "center", padding: 60 }}>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Ready to generate</div>
            <p style={{ marginBottom: 20 }}>
              Click "Generate Report" to create a full AI-powered executive summary
              with insights, trends, and recommendations.
            </p>
            <button className="btn btn-primary" onClick={generateReport}>
              Generate Report
            </button>
          </div>
        )}

        {loading && (
          <div className="card" style={{ textAlign: "center", padding: 60 }}>
            <div className="spinner" style={{ margin: "0 auto 16px", width: 28, height: 28, borderWidth: 3 }} />
            <div style={{ fontWeight: 600, marginBottom: 8 }}>Generating executive report…</div>
            <p>Analysing data, detecting patterns, and writing insights. This may take a moment.</p>
          </div>
        )}

        {/* Report metadata bar */}
        {report && content && (
          <>
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "10px 16px",
              marginBottom: 20,
              fontSize: 12,
              gap: 16,
            }}>
              <div style={{ display: "flex", gap: 24 }}>
                <div>
                  <span className="text-muted">Report ID </span>
                  <span className="text-mono">{report.report_id}</span>
                </div>
                <div>
                  <span className="text-muted">Generated </span>
                  <span>
                    {report.timestamp
                      ? new Date(report.timestamp).toLocaleString()
                      : "just now"}
                  </span>
                </div>
              </div>
              <button
                className="btn btn-secondary btn-sm"
                onClick={downloadReport}
                disabled={downloading}
              >
                {downloading ? "Downloading…" : "Download .md"}
              </button>
            </div>

            {/* Rendered markdown content */}
            <div className="card" style={{ padding: "32px 40px" }}>
              <MarkdownContent content={content} />
            </div>

            {/* Bottom download CTA */}
            <div style={{
              marginTop: 24,
              padding: "20px 24px",
              background: "var(--accent-dim)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 3 }}>Save this report</div>
                <p style={{ fontSize: 13 }}>Download as a Markdown file to share or archive.</p>
              </div>
              <button
                className="btn btn-primary"
                onClick={downloadReport}
                disabled={downloading}
              >
                {downloading ? <><span className="spinner" /> Downloading…</> : "Download Report"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}