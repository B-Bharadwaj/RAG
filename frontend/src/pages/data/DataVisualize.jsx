import { useState, useEffect } from "react";
import { dataApi } from "../../api/client";
import ChartRenderer from "../../components/data/ChartRenderer";
import FileSelector from "../../components/data/FileSelector";
import LoadingDots from "../../components/shared/LoadingDots";

const CHART_TYPES = ["bar", "line", "pie", "hist", "scatter"];

export default function DataVisualize({ activeFileId, onFileSelect }) {
  const [fileId, setFileId] = useState(activeFileId || "");
  const [fileInfo, setFileInfo] = useState(null);

  const [chartType, setChartType] = useState("bar");
  const [xCol, setXCol] = useState("");
  const [yCol, setYCol] = useState("");
  const [chartTitle, setChartTitle] = useState("");
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState("");

  const [anomalies, setAnomalies] = useState([]);
  const [anomalyExplanation, setAnomalyExplanation] = useState("");
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [anomalyError, setAnomalyError] = useState("");

  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  useEffect(() => {
    if (activeFileId) setFileId(activeFileId);
  }, [activeFileId]);

  useEffect(() => {
    if (!fileId) return;
    // FileInfoResponse: file_id, file_name, file_type, sheet_names, row_count, col_count
    dataApi.getFile(fileId)
      .then((r) => setFileInfo(r.data))
      .catch(() => {});
  }, [fileId]);

  const handleSelectFile = (id) => {
    setFileId(id);
    setFileInfo(null);
    setChartData(null);
    setAnomalies([]);
    setAnomalyExplanation("");
    setSummary(null);
    if (onFileSelect) onFileSelect(id);
  };

  const generateChart = async () => {
    if (!fileId) return;
    setChartLoading(true);
    setChartError("");
    setChartData(null);
    try {
      // ChartResponse: chart_id, file_id, title, file_path
      // x_col and y_col are required by backend — validate before sending
      if (!xCol) {
        setChartError("Please select an X column.");
        setChartLoading(false);
        return;
      }
      const res = await dataApi.generateChart(
        fileId, chartType,
        xCol,
        yCol || null,
        chartTitle || null
      );
      // Backend returns file_path for a saved chart image, not inline data
      // We store the response to display what we can
      setChartData(res.data);
    } catch (e) {
      setChartError(e.message);
    } finally {
      setChartLoading(false);
    }
  };

  const loadAnomalies = async () => {
    if (!fileId) return;
    setAnomalyLoading(true);
    setAnomalyError("");
    try {
      // AnomalyResponse: file_id, anomalies[], explanation
      const res = await dataApi.getAnomalies(fileId);
      setAnomalies(res.data?.anomalies || []);
      setAnomalyExplanation(res.data?.explanation || "");
    } catch (e) {
      setAnomalyError(e.message);
    } finally {
      setAnomalyLoading(false);
    }
  };

  const loadSummary = async () => {
    if (!fileId) return;
    setSummaryLoading(true);
    try {
      // SummaryResponse: file_id, summary
      const res = await dataApi.getSummary(fileId);
      setSummary(res.data?.summary || "");
    } catch (e) {
      // silently fail
    } finally {
      setSummaryLoading(false);
    }
  };

  // Backend FileInfoResponse uses sheet_names (not column_names)
  // Columns come from sheet_names for Excel; for CSV there's typically one sheet
  const cols = fileInfo?.column_names || fileInfo?.columns || [];
  const sheets = fileInfo?.sheet_names || [];

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Visualize</h1>
            <p>Build charts, detect anomalies, and get AI-driven insights</p>
          </div>
          <div className="page-header-actions">
            <FileSelector selectedId={fileId} onSelect={handleSelectFile} />
          </div>
        </div>

        {!fileId ? (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Select a file to start visualizing your data.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 20 }}>
            {/* Left: controls */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="card">
                <div className="card-title">Chart Builder</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  <div>
                    <label className="field-label">Chart Type</label>
                    <div className="chip-list">
                      {CHART_TYPES.map((t) => (
                        <button
                          key={t}
                          className={`chip${chartType === t ? " selected" : ""}`}
                          onClick={() => setChartType(t)}
                          style={{ textTransform: "uppercase", fontSize: 11, letterSpacing: "0.04em" }}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="field-label">X Column <span style={{ color: "var(--danger)" }}>*</span></label>
                    {cols.length > 0 ? (
                      <select className="select" value={xCol} onChange={(e) => setXCol(e.target.value)}>
                        <option value="">Select column…</option>
                        {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : (
                      <input
                        className="input"
                        placeholder="e.g. Month, Category, Date"
                        value={xCol}
                        onChange={(e) => setXCol(e.target.value)}
                      />
                    )}
                  </div>

                  <div>
                    <label className="field-label">Y Column</label>
                    {cols.length > 0 ? (
                      <select className="select" value={yCol} onChange={(e) => setYCol(e.target.value)}>
                        <option value="">Auto-detect</option>
                        {cols.map((c) => <option key={c} value={c}>{c}</option>)}
                      </select>
                    ) : (
                      <input
                        className="input"
                        placeholder="e.g. Revenue, Count, Value"
                        value={yCol}
                        onChange={(e) => setYCol(e.target.value)}
                      />
                    )}
                  </div>

                  <div>
                    <label className="field-label">Title (optional)</label>
                    <input
                      className="input"
                      placeholder="Chart title..."
                      value={chartTitle}
                      onChange={(e) => setChartTitle(e.target.value)}
                    />
                  </div>

                  <button
                    className="btn btn-primary"
                    onClick={generateChart}
                    disabled={chartLoading || !xCol}
                  >
                    {chartLoading ? <><span className="spinner" /> Generating…</> : "Generate Chart"}
                  </button>
                </div>
              </div>

              <div className="card">
                <div className="card-title">AI Analysis</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <button className="btn btn-secondary" onClick={loadAnomalies} disabled={anomalyLoading}>
                    {anomalyLoading ? <><span className="spinner" /> Detecting…</> : "Detect Anomalies"}
                  </button>
                  <button className="btn btn-secondary" onClick={loadSummary} disabled={summaryLoading}>
                    {summaryLoading ? <><span className="spinner" /> Summarizing…</> : "Get AI Summary"}
                  </button>
                </div>
              </div>

              {fileInfo && (
                <div className="card">
                  <div className="card-title">File Info</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[
                      ["Name",    fileInfo.file_name],
                      ["Type",    fileInfo.file_type?.toUpperCase()],
                      ["Rows",    fileInfo.row_count?.toLocaleString()],
                      ["Columns", fileInfo.col_count],
                    ].map(([k, v]) => v != null && (
                      <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
                        <span className="text-muted text-sm">{k}</span>
                        <span className="text-sm text-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                  {sheets.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <div className="text-sm text-muted mb-8">Sheets</div>
                      <div className="chip-list">
                        {sheets.map((s) => (
                          <span key={s} className="chip" style={{ fontSize: 11, cursor: "default" }}>{s}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Right: output */}
            <div>
              {chartError && <div className="error-banner mb-12">{chartError}</div>}

              {chartData && (
                <div className="section">
                  <div className="section-title">Chart Output</div>
                  <div className="chart-box">
                    <div style={{ fontWeight: 600, marginBottom: 8 }}>
                      {chartData.title || chartTitle || "Chart Generated"}
                    </div>
                    <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
                      Chart ID: <span className="text-mono">{chartData.chart_id}</span>
                    </div>
                    {chartData.file_path && (
                      <div style={{ marginTop: 12, padding: "10px 14px", background: "var(--bg-elevated)", borderRadius: "var(--radius)", fontSize: 12, color: "var(--text-muted)" }}>
                        Saved to: <span className="text-mono">{chartData.file_path}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {summary && (
                <div className="card mb-16">
                  <div className="card-title">AI Summary</div>
                  <div style={{ color: "var(--text-secondary)", fontSize: 13.5, lineHeight: 1.75 }}>
                    {summary}
                  </div>
                </div>
              )}

              {summaryLoading && (
                <div className="card mb-16" style={{ textAlign: "center", padding: 32 }}>
                  <LoadingDots />
                  <p style={{ marginTop: 12, fontSize: 13 }}>Generating AI summary…</p>
                </div>
              )}

              {anomalyError && <div className="error-banner mb-12">{anomalyError}</div>}

              {(anomalies.length > 0 || anomalyExplanation) && (
                <div className="section">
                  <div className="section-title">Detected Anomalies ({anomalies.length})</div>

                  {anomalyExplanation && (
                    <div className="card mb-12">
                      <div className="card-title">AI Explanation</div>
                      <p style={{ fontSize: 13.5, lineHeight: 1.75 }}>{anomalyExplanation}</p>
                    </div>
                  )}

                  {anomalies.map((a, i) => {
                    const severity = a.severity || "medium";
                    return (
                      <div key={i} className={`anomaly-card ${severity}`}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                          <div className="anomaly-title">
                            {a.column || a.field || `Anomaly ${i + 1}`}
                            {a.row_index != null && (
                              <span className="text-muted text-sm" style={{ marginLeft: 8 }}>
                                Row {a.row_index}
                              </span>
                            )}
                          </div>
                          <span className={`badge ${severity === "high" ? "badge-danger" : severity === "low" ? "badge-info" : "badge-warning"}`}>
                            {severity}
                          </span>
                        </div>
                        <div className="anomaly-desc">{a.description || a.message || "—"}</div>
                        {a.value != null && (
                          <div className="text-mono text-sm" style={{ marginTop: 4 }}>
                            Value: {String(a.value)}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}

              {anomalyLoading && (
                <div className="card" style={{ textAlign: "center", padding: 32 }}>
                  <LoadingDots />
                  <p style={{ marginTop: 12, fontSize: 13 }}>Scanning for anomalies…</p>
                </div>
              )}

              {!chartData && !summary && !anomalies.length && !chartLoading && !summaryLoading && !anomalyLoading && (
                <div className="empty-state" style={{ paddingTop: 60 }}>
                  <div className="empty-state-title">Nothing generated yet</div>
                  <p>Use the controls on the left to generate a chart or run analysis.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}