import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";

export default function PdfManage() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(null);

  const load = async () => {
    setLoading(true);
    try {
      const res = await pdfApi.listDocuments();
      const all = res.data?.documents || res.data || [];
      setDocs(all.filter((d) => (d.file_type || d.type || "pdf").toLowerCase() === "pdf"));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const deleteDoc = async (id) => {
    if (!window.confirm("Delete this document from the index?")) return;
    setDeleting(id);
    try {
      await pdfApi.deleteDocument(id);
      setDocs((d) => d.filter((x) => (x.id || x.doc_id) !== id));
    } catch (e) {
      setError(e.message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Manage Documents</h1>
            <p>{docs.length} document{docs.length !== 1 ? "s" : ""} indexed</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-secondary btn-sm" onClick={load}>
              Refresh
            </button>
          </div>
        </div>

        {error && <div className="error-banner mb-16">{error}</div>}

        {loading ? (
          <div className="empty-state">
            <div className="spinner" style={{ margin: "0 auto 12px" }} />
            Loading documents…
          </div>
        ) : docs.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No documents indexed</div>
            <p>Upload PDFs in the Upload tab to get started.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Filename</th>
                  <th>Document ID</th>
                  <th>Chunks</th>
                  <th>Uploaded</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {docs.map((d) => {
                  const id = d.id || d.doc_id;
                  return (
                    <tr key={id}>
                      <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                        {d.filename || d.title || "—"}
                      </td>
                      <td className="text-mono text-sm">{id}</td>
                      <td className="text-mono">{d.chunks ?? d.chunk_count ?? "—"}</td>
                      <td className="text-sm">
                        {d.created_at
                          ? new Date(d.created_at).toLocaleDateString()
                          : "—"}
                      </td>
                      <td>
                        <span className="badge badge-success">Indexed</span>
                      </td>
                      <td style={{ textAlign: "right" }}>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => deleteDoc(id)}
                          disabled={deleting === id}
                        >
                          {deleting === id ? <span className="spinner" /> : "Delete"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}