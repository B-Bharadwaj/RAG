import { useState, useEffect } from "react";
import { dataApi } from "../../api/client";

export default function DataManage({ onFileSelect }) {
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(null);
  const [selectedId, setSelectedId] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await dataApi.listFiles();
      const all = res.data || [];
      setFiles(all.filter((f) => ["csv", "xlsx", "xls"].includes((f.file_type || "").toLowerCase())));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // No window.confirm
  const deleteFile = async (id) => {
    setDeleting(id);
    try {
      await dataApi.deleteFile(id);
      setFiles((f) => f.filter((x) => x.file_id !== id));
      if (selectedId === id) setSelectedId(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(null);
    }
  };

  const setActive = (id) => {
    setSelectedId(id);
    if (onFileSelect) onFileSelect(id);
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Manage Files</h1>
            <p>{files.length} file{files.length !== 1 ? "s" : ""} uploaded</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-secondary btn-sm" onClick={load}>Refresh</button>
          </div>
        </div>

        {error && <div className="error-banner mb-16">{error}</div>}

        <div className="kpi-grid mb-24">
          <div className="kpi-card">
            <div className="kpi-label">Total Files</div>
            <div className="kpi-value">{files.length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Total Rows</div>
            <div className="kpi-value">{files.reduce((a, f) => a + (f.row_count || 0), 0).toLocaleString()}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">CSV Files</div>
            <div className="kpi-value">{files.filter((f) => f.file_type === "csv").length}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Excel Files</div>
            <div className="kpi-value">{files.filter((f) => f.file_type === "xlsx" || f.file_type === "xls").length}</div>
          </div>
        </div>

        {loading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto 12px" }} />Loading files…</div>
        ) : files.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No files uploaded yet</div>
            <p>Go to Upload to add CSV or Excel files.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>File Name</th>
                  <th>Type</th>
                  <th>Rows</th>
                  <th>Columns</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {files.map((f) => {
                  const id = f.file_id;
                  const isActive = selectedId === id;
                  const typeColor = f.file_type === "csv" ? "badge-info" : "badge-success";
                  return (
                    <tr key={id} style={{ cursor: "pointer", background: isActive ? "var(--accent-glow)" : undefined }} onClick={() => setActive(id)}>
                      <td style={{ width: 200, maxWidth: 200, overflow: "hidden" }}>
  <div style={{ fontWeight: 600, color: "var(--text-primary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={f.file_name}>
    {f.file_name}
  </div>
  <div className="text-mono text-sm text-muted">{id}</div>
</td>
                      <td><span className={`badge ${typeColor}`}>{(f.file_type || "—").toUpperCase()}</span></td>
                      <td className="text-mono">{f.row_count?.toLocaleString() ?? "—"}</td>
                      <td className="text-mono">{f.col_count ?? "—"}</td>
                      <td className="text-sm">{f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "—"}</td>
                      <td>{isActive ? <span className="badge badge-success">Active</span> : <span className="badge badge-neutral">Ready</span>}</td>
                      <td style={{ textAlign: "right" }} onClick={(e) => e.stopPropagation()}>
                        <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                          <button className="btn btn-secondary btn-sm" onClick={() => setActive(id)}>{isActive ? "Selected" : "Select"}</button>
                          <button className="btn btn-danger btn-sm" onClick={() => deleteFile(id)} disabled={deleting === id}>
                            {deleting === id ? <span className="spinner" /> : "Delete"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {selectedId && (
          <div className="success-banner mt-16">File set as active — available in Chat, Visualize, and Report.</div>
        )}
      </div>
    </div>
  );
}