import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";

function PaperCard({ doc }) {
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState(false);

  const generateSummary = async () => {
    setLoading(true);
    try {
      const res = await pdfApi.getDocumentSummary(doc.doc_id);
      setSummary(
        res.data?.summary || res.data?.abstract || "No summary available."
      );
      setGenerated(true);
    } catch (e) {
      setSummary("Failed to generate summary: " + e.message);
      setGenerated(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card mb-12">
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 3, color: "var(--text-primary)" }}>
            {doc.title || doc.filename}
          </div>
          <div className="text-sm text-muted">{doc.authors || "Unknown authors"}</div>
          <div className="text-mono text-sm" style={{ color: "var(--text-disabled)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={doc.filename}>
  {doc.filename} · {doc.page_count || "?"} pages · {doc.chunk_count || "?"} chunks
</div>
        </div>
        <button
          type="button"
          className="btn btn-secondary btn-sm"
          onClick={generateSummary}
          disabled={loading}
          style={{ flexShrink: 0 }}
        >
          {loading ? (
            <><span className="spinner" /> Generating…</>
          ) : generated ? (
            "Refresh"
          ) : (
            "Generate Summary"
          )}
        </button>
      </div>

      {loading && (
        <div style={{ marginTop: 14, fontSize: 13, color: "var(--text-muted)" }}>
          Generating summary — first time takes 10–15 seconds…
        </div>
      )}

      {summary && !loading && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--border)" }}>
          <div className="section-title" style={{ marginBottom: 8 }}>Summary</div>
          <p style={{ fontSize: 13.5, lineHeight: 1.8, color: "var(--text-secondary)", whiteSpace: "pre-wrap" }}>
            {summary}
          </p>
        </div>
      )}
    </div>
  );
}

export default function PdfReport() {
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    pdfApi.listDocuments()
      .then((r) => setDocs(r.data?.documents || r.data || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Paper Summaries</h1>
            <p>AI-generated summaries for each indexed document</p>
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
          docs.map((doc) => <PaperCard key={doc.doc_id} doc={doc} />)
        )}
      </div>
    </div>
  );
}