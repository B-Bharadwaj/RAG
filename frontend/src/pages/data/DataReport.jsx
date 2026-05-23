import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { dataApi } from "../../api/client";
import FileSelector from "../../components/data/FileSelector";
import LoadingDots from "../../components/shared/LoadingDots";

const mdComponents = {
  h1: ({ children }) => <h1 style={{ color: "var(--text-primary)", margin: "20px 0 10px", fontSize: 18 }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ color: "var(--text-primary)", margin: "18px 0 8px", fontSize: 15 }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ color: "var(--text-primary)", margin: "14px 0 6px", fontSize: 13 }}>{children}</h3>,
  p: ({ children }) => <p style={{ color: "var(--text-secondary)", lineHeight: 1.8, marginBottom: 10, fontSize: 13.5 }}>{children}</p>,
  ul: ({ children }) => <ul style={{ paddingLeft: 20, marginBottom: 10, color: "var(--text-secondary)", fontSize: 13.5 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ paddingLeft: 20, marginBottom: 10, color: "var(--text-secondary)", fontSize: 13.5 }}>{children}</ol>,
  li: ({ children }) => <li style={{ marginBottom: 5, lineHeight: 1.7 }}>{children}</li>,
  strong: ({ children }) => <strong style={{ color: "var(--text-primary)", fontWeight: 600 }}>{children}</strong>,
  hr: () => <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />,
  code: ({ inline, children }) => inline
    ? <code style={{ background: "var(--bg-elevated)", padding: "2px 6px", borderRadius: 3, fontSize: 12, fontFamily: "var(--font-mono)", color: "var(--brand-primary)" }}>{children}</code>
    : <pre style={{ background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "12px 16px", overflowX: "auto", marginBottom: 12 }}><code style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text-secondary)" }}>{children}</code></pre>,
};

export default function DataReport({ activeFileId, onFileSelect }) {
  const [fileId, setFileId] = useState(activeFileId || "");
  const [fileValid, setFileValid] = useState(null);

  const [summary, setSummary] = useState("");
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState("");

  const [report, setReport] = useState(null);
  const [reportContent, setReportContent] = useState("");
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [anomalyText, setAnomalyText] = useState("");
  const [anomalyLoading, setAnomalyLoading] = useState(false);

  const loadAnomalies = async () => {
    setAnomalyLoading(true);
    setAnomalyText("");
    try {
      const res = await dataApi.getAnomalies(fileId);
      setAnomalyText(res.data?.explanation || "No anomalies detected.");
    } catch (e) {
      setAnomalyText("Failed: " + e.message);
    } finally {
      setAnomalyLoading(false);
    }
  };

  useEffect(() => { if (activeFileId) setFileId(activeFileId); }, [activeFileId]);

  useEffect(() => {
    if (!fileId) { setFileValid(null); return; }
    setFileValid(null);
    setSummary("");
    setReport(null);
    setReportContent("");
    dataApi.getFile(fileId)
      .then(() => setFileValid(true))
      .catch(() => setFileValid(false));
  }, [fileId]);

  const handleSelectFile = (id) => {
    setFileId(id);
    if (onFileSelect) onFileSelect(id);
  };

  const generateSummary = async () => {
    setSummaryLoading(true);
    setSummaryError("");
    setSummary("");
    try {
      const res = await dataApi.getSummary(fileId);
      setSummary(res.data?.summary || "No summary generated.");
    } catch (e) {
      setSummaryError(e.message);
    } finally {
      setSummaryLoading(false);
    }
  };

  const generateReport = async () => {
    setReportLoading(true);
    setReportError("");
    setReport(null);
    setReportContent("");
    try {
      const res = await dataApi.getReport(fileId);
      const meta = res.data;
      setReport(meta);
      const dlRes = await dataApi.downloadReport(meta.report_id);
      const text = await dlRes.data.text();
      setReportContent(text);
    } catch (e) {
      setReportError(e.message);
    } finally {
      setReportLoading(false);
    }
  };

  const downloadMarkdown = () => {
    if (!reportContent || !report) return;
    setDownloading(true);
    const blob = new Blob([reportContent], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report_${report.report_id}.md`;
    a.click();
    URL.revokeObjectURL(url);
    setDownloading(false);
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Executive Report</h1>
            <p>SQL-driven analysis and AI-generated business intelligence report</p>
          </div>
          <div className="page-header-actions">
            <FileSelector selectedId={fileId} onSelect={handleSelectFile} />
          </div>
        </div>

        {!fileId && (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Select a file to generate reports.</p>
          </div>
        )}

        {fileId && fileValid === false && (
          <div className="error-banner mb-16">
            File not found in backend. Please re-upload your file in the Upload tab.
          </div>
        )}

        {fileId && fileValid === true && (
          <>
            {/* ── Section 1: Executive Summary ── */}
            <div className="card mb-20">
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 16 }}>
                <div>
                  <h2 style={{ marginBottom: 3 }}>Executive Summary</h2>
                  <p style={{ fontSize: 12 }}>
                    SQL-driven analysis — Dataset Overview, Key Findings, Notable Patterns, Data Quality
                  </p>
                </div>
                <button
                  className="btn btn-primary btn-sm"
                  onClick={generateSummary}
                  disabled={summaryLoading}
                  style={{ flexShrink: 0 }}
                >
                  {summaryLoading ? <><span className="spinner" /> Running SQL analysis…</> : "Generate Summary"}
                </button>
              </div>

              {summaryError && <div className="error-banner mb-12">{summaryError}</div>}

              {!summary && !summaryLoading && (
                <div style={{ textAlign: "center", padding: "28px 0", color: "var(--text-muted)", fontSize: 13 }}>
                  Click "Generate Summary" to run SQL analysis on your dataset.
                </div>
              )}

              {summaryLoading && (
                <div style={{ textAlign: "center", padding: "28px 0" }}>
                  <div className="spinner" style={{ margin: "0 auto 10px" }} />
                  <p style={{ fontSize: 13 }}>Running SQL analysis…</p>
                </div>
              )}

              {summary && (
                <div style={{ paddingTop: 4 }}>
                  <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                    {summary}
                  </ReactMarkdown>
                </div>
              )}

              {/* Panel 2: Data Quality / Anomaly Detection */}
              <div className="card">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: anomalyText ? 14 : 0 }}>
                  <div>
                    <div className="card-title" style={{ margin: 0 }}>Data Quality</div>
                  </div>
                  <button className="btn btn-secondary btn-sm" onClick={loadAnomalies} disabled={anomalyLoading}>
                    {anomalyLoading ? <><span className="spinner" /> Detecting…</> : "Run Anomaly Detection"}
                  </button>
                </div>

                {anomalyLoading && (
                  <div style={{ textAlign: "center", padding: "20px 0" }}>
                    <LoadingDots />
                  </div>
                )}

                {anomalyText && !anomalyLoading && (
                  <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}
                      components={{
                        p: ({ children }) => <p style={{ color: "var(--text-secondary)", fontSize: 13.5, lineHeight: 1.75, marginBottom: 8 }}>{children}</p>,
                        ul: ({ children }) => <ul style={{ paddingLeft: 18, color: "var(--text-secondary)", fontSize: 13.5 }}>{children}</ul>,
                        li: ({ children }) => <li style={{ marginBottom: 4, lineHeight: 1.6 }}>{children}</li>,
                        strong: ({ children }) => <strong style={{ color: "var(--text-primary)" }}>{children}</strong>,
                      }}>
                      {anomalyText}
                    </ReactMarkdown>
                  </div>
                )}
                {!anomalyText && !anomalyLoading && (
                  <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 10 }}>
                    Click "Run Anomaly Detection" to analyse your data for outliers and quality issues.
                  </p>
                )}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}