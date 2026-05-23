import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";
import MarkdownContent from "../../components/shared/MarkdownContent";

export default function PdfCompare({ compareHistory, setCompareHistory }) {
  const [docs, setDocs] = useState([]);
  const [selected, setSelected] = useState([]);
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    pdfApi.listDocuments()
      .then((r) => setDocs(r.data?.documents || r.data || []))
      .catch(() => { });
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
      const entry = {
        question: question.trim(),
        answer: res.data.answer,
        sources: res.data.sources || [],
        doc_ids: selected,
        timestamp: new Date().toISOString(),
      };
      setResult(entry);
      setCompareHistory((prev) => [entry, ...prev]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const clearHistory = () => setCompareHistory([]);

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Compare Papers</h1>
            <p>Select 2–3 documents and ask a comparison question</p>
          </div>
          {compareHistory.length > 0 && (
            <button className="btn btn-ghost btn-sm" onClick={clearHistory}>Clear History</button>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {/* Left */}
          <div>
            <div className="section">
              <div className="section-title">Select Documents ({selected.length}/3)</div>
              {docs.length === 0 ? (
                <div className="card"><p style={{ fontSize: 13 }}>No documents indexed yet. Upload PDFs first.</p></div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {docs.map((d) => {
                    const id = d.id || d.doc_id;
                    const isSelected = selected.includes(id);
                    return (
                      <div key={id}
                        className="card"
                        style={{ cursor: "pointer", padding: "12px 16px", borderColor: isSelected ? "var(--accent)" : "var(--border)", background: isSelected ? "var(--accent-glow)" : "var(--bg-surface)", transition: "all var(--transition)" }}
                        onClick={() => toggle(id)}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div>
                            <div style={{ fontWeight: 600, fontSize: 13 }}>{d.filename || d.title || "Document"}</div>
                            <div className="text-sm text-muted text-mono">{id}</div>
                          </div>
                          {isSelected && <span className="badge badge-info">#{selected.indexOf(id) + 1}</span>}
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
                placeholder="e.g. How do these papers approach evaluation differently?"
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
            {selected.length < 2 && <p className="text-sm text-muted mt-8">Select at least 2 documents to compare.</p>}
          </div>

          {/* Right */}
          <div>
            <div className="section-title">Results</div>
            {error && <div className="error-banner mb-12">{error}</div>}
            {loading && <div className="card" style={{ padding: 40, textAlign: "center" }}><LoadingDots /><p style={{ marginTop: 12, fontSize: 13 }}>Analysing documents…</p></div>}

            {!loading && compareHistory.length === 0 && !error && (
              <div className="empty-state" style={{ paddingTop: 40 }}>
                <div className="empty-state-title">No comparisons yet</div>
                <p>Select documents and ask a question to see results.</p>
              </div>
            )}

            {compareHistory.map((entry, i) => (
              <div key={i} className="card mb-12">
                <div style={{ fontWeight: 600, marginBottom: 6, fontSize: 13 }}>{entry.question}</div>
                <div className="text-sm text-muted mb-12">
                  {new Date(entry.timestamp).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                </div>
                <div className="divider" />
                <div style={{ marginTop: 12 }}>
                  <MarkdownContent content={entry.answer} />
                </div>
                {entry.sources?.length > 0 && (
                  <>
                    <div className="divider" />
                    <div className="section-title">Sources</div>
                    <div className="sources-list">
                      {entry.sources.map((s, si) => (
                        <div key={si} className="source-chip">
                          <span className="source-chip-score">{s.doc_id || `src ${si + 1}`}</span>
                          <span>{s.filename || s.source || s.pdf || s.text?.slice(0, 60) || ""}</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}