import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";

export default function PdfCompare() {
  const [docs, setDocs] = useState([]);
  const [selected, setSelected] = useState([]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    pdfApi.listDocuments()
      .then((r) => setDocs(r.data?.documents || r.data || []))
      .catch(() => {});
  }, []);

  const toggle = (id) => {
    setSelected((prev) => {
      if (prev.includes(id)) return prev.filter((x) => x !== id);
      if (prev.length >= 3) return prev;
      return [...prev, id];
    });
  };

  const compare = async () => {
    if (selected.length < 2 || !question.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await pdfApi.compare(selected, question.trim());
      setResult(res.data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Compare Papers</h1>
            <p>Select 2–3 documents and ask a comparison question</p>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Left: Selection */}
          <div>
            <div className="section">
              <div className="section-title">Select Documents ({selected.length}/3)</div>
              {docs.length === 0 ? (
                <div className="card">
                  <p style={{ fontSize: 13 }}>No documents indexed yet. Upload PDFs first.</p>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {docs.map((d) => {
                    const id = d.id || d.doc_id;
                    const isSelected = selected.includes(id);
                    return (
                      <div
                        key={id}
                        className={`card${isSelected ? " selected" : ""}`}
                        style={{
                          cursor: "pointer",
                          padding: "12px 16px",
                          borderColor: isSelected ? "var(--accent)" : "var(--border)",
                          background: isSelected ? "var(--accent-glow)" : "var(--bg-surface)",
                          transition: "all var(--transition)",
                        }}
                        onClick={() => toggle(id)}
                      >
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>
                              {d.filename || d.title || "Document"}
                            </div>
                            <div className="text-sm text-muted text-mono">{id}</div>
                          </div>
                          {isSelected && (
                            <span className="badge badge-info">
                              #{selected.indexOf(id) + 1}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="section">
              <label className="field-label">Comparison Question</label>
              <textarea
                className="textarea"
                placeholder="e.g. How do these papers approach evaluation methodology differently?"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
              />
            </div>

            <button
              className="btn btn-primary w-full"
              onClick={compare}
              disabled={selected.length < 2 || !question.trim() || loading}
            >
              {loading ? <><span className="spinner" /> Comparing…</> : "Compare Selected Papers"}
            </button>

            {selected.length < 2 && (
              <p className="text-sm text-muted mt-8">Select at least 2 documents to compare.</p>
            )}
          </div>

          {/* Right: Result */}
          <div>
            <div className="section-title">Comparison Result</div>
            {error && <div className="error-banner mb-12">{error}</div>}
            {loading && (
              <div className="card" style={{ padding: "40px", textAlign: "center" }}>
                <LoadingDots />
                <p style={{ marginTop: 12, fontSize: 13 }}>Analyzing documents…</p>
              </div>
            )}
            {!loading && !result && !error && (
              <div className="empty-state" style={{ paddingTop: 40 }}>
                <div className="empty-state-title">No comparison yet</div>
                <p>Select documents and ask a question to see results.</p>
              </div>
            )}
            {result && (
              <div className="card">
                <div className="card-title">Analysis</div>
                <div style={{ color: "var(--text-secondary)", fontSize: 13.5, lineHeight: 1.75, whiteSpace: "pre-wrap" }}>
                  {result.answer || result.comparison || JSON.stringify(result, null, 2)}
                </div>
                {result.sources?.length > 0 && (
                  <>
                    <div className="divider" />
                    <div className="section-title">Sources</div>
                    <div className="sources-list">
                      {result.sources.map((s, i) => (
                        <div key={i} className="source-chip">
                          <span className="source-chip-score">{s.doc_id || `src ${i+1}`}</span>
                          <span>{s.filename || s.source || s.text?.slice(0, 60) || ""}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}