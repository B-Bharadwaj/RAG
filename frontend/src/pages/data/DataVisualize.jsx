import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { dataApi } from "../../api/client";
import ChartRenderer from "../../components/data/ChartRenderer";
import FileSelector from "../../components/data/FileSelector";
import LoadingDots from "../../components/shared/LoadingDots";

const CHART_TYPES = ["bar", "line", "pie", "hist", "scatter"];
const AGGREGATIONS = ["count", "sum", "average", "min", "max"];

export default function DataVisualize({ activeFileId, onFileSelect }) {
  const [fileId, setFileId] = useState(
  activeFileId || localStorage.getItem("ragbot_active_file_id") || ""
);
  const [fileInfo, setFileInfo] = useState(null);
  const [columns, setColumns] = useState([]);
  const [colsLoading, setColsLoading] = useState(false);

  // Chart builder
  const [chartType, setChartType] = useState("bar");
  const [xCol, setXCol] = useState("");
  const [yCol, setYCol] = useState("");
  const [aggregation, setAggregation] = useState("count");
  const [filterValues, setFilterValues] = useState([]);
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState("");

  // AI panels
  const [anomalyText, setAnomalyText] = useState("");
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [fileInsights, setFileInsights] = useState("");

  useEffect(() => { if (activeFileId) setFileId(activeFileId); }, [activeFileId]);

  useEffect(() => {
    if (!fileId) return;
    setColumns([]);
    setXCol("");
    setYCol("");
    setFilterValues([]);
    setChartData(null);
    setAnomalyText("");

    dataApi.getFile(fileId)
      .then((r) => {
        setFileInfo(r.data);
        // Show insights from file info if present
        if (r.data?.insights) setFileInsights(r.data.insights);
      })
      .catch(() => { });

    setColsLoading(true);
    dataApi.getColumnValues(fileId)
      .then((r) => setColumns(r.data?.columns || []))
      .catch(() => { })
      .finally(() => setColsLoading(false));
  }, [fileId]);

  const handleSelectFile = (id) => {
    setFileId(id);
    setFileInfo(null);
    setChartData(null);
    if (onFileSelect) onFileSelect(id);
  };

  const xColMeta = columns.find((c) => c.name === xCol);
  const isCategorical = xColMeta?.type === "categorical";
  const showCheckboxes = isCategorical && (xColMeta?.unique_count || 0) <= 50;
  const showTextFilter = isCategorical && (xColMeta?.unique_count || 0) > 50;
  const showYCol = aggregation !== "count";
  const numericCols = columns.filter((c) => c.type === "numeric");

  const toggleFilter = (val) =>
    setFilterValues((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  const selectAllFilters = () =>
    setFilterValues(xColMeta?.unique_values?.map(String) || []);
  const clearFilters = () => setFilterValues([]);

  const generateChart = async () => {
    if (!fileId || !xCol) { setChartError("Please select an X column."); return; }
    setChartLoading(true);
    setChartError("");
    setChartData(null);
    try {
      const res = await dataApi.generateChart(
        fileId,
        chartType,
        xCol,
        showYCol ? (yCol || null) : null,
        null,            // title — let backend auto-title
        aggregation,
        isCategorical && filterValues.length ? xCol : null,  // filter_col
        filterValues,    // filter_values (empty = all)
      );
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
    setAnomalyText("");
    try {
      const res = await dataApi.getAnomalies(fileId);
      setAnomalyText(res.data?.explanation || "No anomalies detected.");
    } catch (e) {
      setAnomalyText("Failed to load anomaly analysis: " + e.message);
    } finally {
      setAnomalyLoading(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Visualize</h1>
            <p>SQL-powered chart builder with AI insights</p>
          </div>
          <div className="page-header-actions">
            <FileSelector selectedId={fileId} onSelect={handleSelectFile} />
          </div>
        </div>

        {!fileId ? (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Select a file to start visualizing.</p>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 20 }}>

            {/* ── Left controls ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="card">
                <div className="card-title">Chart Builder</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

                  {/* Row 1: Chart type */}
                  <div>
                    <label className="field-label">Chart Type</label>
                    <div className="chip-list">
                      {CHART_TYPES.map((t) => (
                        <button key={t} className={`chip${chartType === t ? " selected" : ""}`}
                          onClick={() => setChartType(t)}
                          style={{ textTransform: "uppercase", fontSize: 11 }}>
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Row 2: X column */}
                  <div>
                    <label className="field-label">
                      X Axis Column <span style={{ color: "var(--danger)" }}>*</span>
                      {colsLoading && <span className="text-muted" style={{ fontSize: 10, marginLeft: 6 }}>loading…</span>}
                    </label>
                    <select className="select" value={xCol}
                      onChange={(e) => { setXCol(e.target.value); setFilterValues([]); }}>
                      <option value="">Select column…</option>
                      {columns.map((c) => (
                        <option key={c.name} value={c.name}>
                          {c.name} ({c.type}{c.unique_count ? `, ${c.unique_count} unique` : ""})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Row 3: Filter values (categorical only, ≤50 unique) */}
                  {showCheckboxes && xColMeta?.unique_values?.length > 0 && (
                    <div>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                        <label className="field-label" style={{ margin: 0 }}>
                          Filter Values
                          <span className="text-muted" style={{ fontSize: 10, marginLeft: 6 }}>
                            ({filterValues.length === 0 ? "all" : `${filterValues.length} selected`})
                          </span>
                        </label>
                        <div style={{ display: "flex", gap: 8 }}>
                          <button type="button" onClick={selectAllFilters} style={{ fontSize: 11, color: "var(--brand-primary)", background: "none", border: "none", cursor: "pointer", padding: 0 }}>All</button>
                          <button type="button" onClick={clearFilters} style={{ fontSize: 11, color: "var(--text-muted)", background: "none", border: "none", cursor: "pointer", padding: 0 }}>Clear</button>
                        </div>
                      </div>
                      <div style={{ maxHeight: 180, overflowY: "auto", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "8px 10px", background: "var(--bg-elevated)", display: "flex", flexDirection: "column", gap: 6 }}>
                        {xColMeta.unique_values.map((val) => (
                          <label key={String(val)} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, cursor: "pointer" }}>
                            <input
                              type="checkbox"
                              checked={filterValues.includes(String(val))}
                              onChange={() => toggleFilter(String(val))}
                              style={{ accentColor: "var(--brand-primary)" }}
                            />
                            {String(val)}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Text filter for high-cardinality */}
                  {showTextFilter && (
                    <div>
                      <label className="field-label">Filter Value (text match)</label>
                      <input
                        className="input"
                        placeholder="Type a value to filter…"
                        value={filterValues[0] || ""}
                        onChange={(e) => setFilterValues(e.target.value ? [e.target.value] : [])}
                      />
                    </div>
                  )}

                  {/* Row 4: Aggregation */}
                  <div>
                    <label className="field-label">Aggregation</label>
                    <select className="select" value={aggregation} onChange={(e) => setAggregation(e.target.value)}>
                      {AGGREGATIONS.map((a) => (
                        <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
                      ))}
                    </select>
                  </div>

                  {/* Row 5: Y column (only for sum/average/min/max) */}
                  {showYCol && (
                    <div>
                      <label className="field-label">Y Axis Column</label>
                      <select className="select" value={yCol} onChange={(e) => setYCol(e.target.value)}>
                        <option value="">Auto-detect numeric</option>
                        {numericCols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
                      </select>
                    </div>
                  )}

                  {/* Row 6: Generate */}
                  <button className="btn btn-primary" onClick={generateChart} disabled={chartLoading || !xCol}>
                    {chartLoading ? <><span className="spinner" /> Generating…</> : "Generate Chart"}
                  </button>
                </div>
              </div>

              {/* File info */}
              {fileInfo && (
                <div className="card">
                  <div className="card-title">File Info</div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {[["Name", fileInfo.file_name], ["Type", fileInfo.file_type?.toUpperCase()], ["Rows", fileInfo.row_count?.toLocaleString()], ["Columns", fileInfo.col_count]]
                      .filter(([, v]) => v != null)
                      .map(([k, v]) => (
                        <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
                          <span className="text-muted text-sm">{k}</span>
                          <span className="text-sm text-mono">{v}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
            </div>

            {/* ── Right output ── */}
            <div>
              {chartError && <div className="error-banner mb-12">{chartError}</div>}
              {chartLoading && (
                <div className="card mb-16" style={{ textAlign: "center", padding: 40 }}>
                  <LoadingDots />
                  <p style={{ marginTop: 12, fontSize: 13 }}>Running SQL query…</p>
                </div>
              )}

              {chartData && (
                <div className="section mb-16">
                  <div className="section-title">Chart</div>
                  <ChartRenderer chart={chartData} height={400} />
                </div>
              )}

              {/* Panel 1: AI Insights from upload */}
              {fileInsights && (
                <div className="card mb-16">
                  <div className="card-title">AI Insights</div>
                  <p style={{ fontSize: 13.5, lineHeight: 1.8, color: "var(--text-secondary)" }}>{fileInsights}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}