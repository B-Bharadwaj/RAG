import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";

function ScoreCell({ score }) {
  if (score == null) return <span style={{ color: "var(--text-disabled)" }}>—</span>;
  const pct = typeof score === "number" && score <= 1 ? score : score / 100;
  const display = pct.toFixed(4);
  const color = pct >= 0.7 ? "var(--success)" : pct >= 0.4 ? "var(--warning)" : "var(--danger)";
  return <span style={{ fontFamily: "var(--font-mono)", color, fontWeight: 600 }}>{display}</span>;
}

function FailureAccordion({ item, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      border: "1px solid var(--border)",
      borderRadius: "var(--radius)",
      overflow: "hidden",
      marginBottom: 8,
    }}>
      <div
        onClick={() => setOpen(!open)}
        style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "12px 16px", cursor: "pointer",
          background: "var(--bg-elevated)",
          userSelect: "none",
        }}
      >
        <span style={{ color: "var(--text-muted)", fontSize: 13, transition: "transform 0.2s", display: "inline-block", transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>›</span>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{item.query || item.question || `Query ${index + 1}`}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {item.faithfulness != null && (
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: item.faithfulness < 0.5 ? "var(--danger)" : "var(--success)" }}>
              F:{item.faithfulness.toFixed(2)}
            </span>
          )}
          {item.relevancy != null && (
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: item.relevancy < 0.5 ? "var(--danger)" : "var(--success)" }}>
              R:{item.relevancy.toFixed(2)}
            </span>
          )}
          {item.context_recall != null && (
            <span style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: item.context_recall < 0.5 ? "var(--danger)" : "var(--success)" }}>
              C:{item.context_recall.toFixed(2)}
            </span>
          )}
        </div>
      </div>
      {open && (
        <div style={{ padding: "14px 16px", borderTop: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          {item.reasoning && (
            <div style={{ marginBottom: 10 }}>
              <div className="text-sm text-muted mb-8">Reasoning</div>
              <p style={{ fontSize: 13, lineHeight: 1.7 }}>{item.reasoning}</p>
            </div>
          )}
          {item.answer && (
            <div style={{ marginBottom: 10 }}>
              <div className="text-sm text-muted mb-8">Answer</div>
              <p style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text-secondary)" }}>{item.answer}</p>
            </div>
          )}
          {item.scope && (
            <div>
              <div className="text-sm text-muted mb-8">Scope</div>
              <span className="badge badge-neutral text-mono" style={{ fontSize: 11 }}>{item.scope}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function PdfEval() {
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scoring, setScoring] = useState(false);
  const [scoreMsg, setScoreMsg] = useState("");
  const [limit, setLimit] = useState(5);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await pdfApi.getEvalResults();
      const raw = res.data?.results || res.data?.scores || res.data?.evals || res.data;
      setResults(Array.isArray(raw) ? raw : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const scoreNow = async () => {
    setScoring(true);
    setScoreMsg("");
    setError("");
    try {
      // Call score endpoint with limit — backend pulls from DB automatically
      await pdfApi.scoreQuery(limit);
      setScoreMsg(`Scored ${limit} queries successfully.`);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setScoring(false);
    }
  };

  const clearAll = async () => {
    if (!window.confirm("Clear all evaluation scores?")) return;
    await pdfApi.clearEvalResults().catch(() => {});
    setResults([]);
    setScoreMsg("");
  };

  // Aggregates
  const avg = (key) => {
    const vals = results.map((r) => r[key]).filter((v) => v != null && typeof v === "number");
    if (!vals.length) return null;
    return vals.reduce((a, b) => a + b, 0) / vals.length;
  };

  const avgFaith   = avg("faithfulness");
  const avgRel     = avg("relevancy") ?? avg("relevance") ?? avg("answer_relevance");
  const avgContext = avg("context_recall") ?? avg("context_precision");

  const failures = results.filter((r) =>
    (r.faithfulness != null && r.faithfulness < 0.5) ||
    (r.relevancy != null && r.relevancy < 0.5) ||
    (r.context_recall != null && r.context_recall < 0.5)
  );

  return (
    <div className="page-content">
      <div className="page-inner">

        {/* Header */}
        <div className="page-header">
          <div className="page-header-left">
            <h1>RAG Evaluation Dashboard</h1>
            <p>
              Judge LLM scores each response across Faithfulness, Answer Relevancy, and Context Recall.
            </p>
          </div>
        </div>

        {error && <div className="error-banner mb-16">{error}</div>}
        {scoreMsg && <div className="success-banner mb-16">{scoreMsg}</div>}

        {/* Score Now panel */}
        <div className="card mb-24">
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>
              Queries to score (most recent un-scored)
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <input
                type="range"
                min={1}
                max={20}
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                style={{ flex: 1, accentColor: "var(--accent)" }}
              />
              <span className="text-mono" style={{ minWidth: 24, textAlign: "center", fontWeight: 600 }}>
                {limit}
              </span>
              <button
                className="btn btn-primary"
                onClick={scoreNow}
                disabled={scoring}
                style={{ minWidth: 140 }}
              >
                {scoring ? <><span className="spinner" /> Scoring…</> : "Score Now"}
              </button>
            </div>
          </div>
        </div>

        <div className="divider" />

        {/* KPIs */}
        <div className="section-title mt-16">KPIs</div>
        <div className="kpi-grid mb-24">
          {[
            { label: "Avg Faithfulness",   value: avgFaith   != null ? avgFaith.toFixed(4)   : "—" },
            { label: "Avg Relevancy",      value: avgRel     != null ? avgRel.toFixed(4)     : "—" },
            { label: "Avg Context Recall", value: avgContext  != null ? avgContext.toFixed(4) : "—" },
            { label: "Total scored",       value: results.length },
          ].map((k) => (
            <div key={k.label} className="kpi-card">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value" style={{ fontSize: 22 }}>{k.value}</div>
            </div>
          ))}
        </div>

        <div className="divider" />

        {/* Score history table */}
        <div style={{ fontWeight: 600, fontSize: 15, margin: "20px 0 12px" }}>Score history</div>

        {loading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : results.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No scores yet</div>
            <p>Click "Score Now" to evaluate recent queries from the database.</p>
          </div>
        ) : (
          <div className="table-wrap mb-24">
            <table>
              <thead>
                <tr>
                  <th>Query</th>
                  <th>Faithfulness</th>
                  <th>Relevancy</th>
                  <th>Context Recall</th>
                  <th>Reasoning</th>
                  <th>Scope</th>
                  <th>Scored At</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i}>
                    <td style={{ maxWidth: 160 }}>
                      <div className="truncate" style={{ fontWeight: 500, color: "var(--text-primary)" }} title={r.query || r.question}>
                        {r.query || r.question || "—"}
                      </div>
                    </td>
                    <td><ScoreCell score={r.faithfulness} /></td>
                    <td><ScoreCell score={r.relevancy ?? r.relevance ?? r.answer_relevance} /></td>
                    <td><ScoreCell score={r.context_recall ?? r.context_precision} /></td>
                    <td style={{ maxWidth: 320 }}>
                      <div className="truncate text-sm" title={r.reasoning}>{r.reasoning || "—"}</div>
                    </td>
                    <td className="text-mono text-sm">
                      {r.scope || r.doc_id || "All PDFs"}
                    </td>
                    <td className="text-sm text-muted">
                      {r.scored_at || r.created_at
                        ? new Date(r.scored_at || r.created_at).toLocaleString(undefined, {
                            month: "short", day: "numeric",
                            hour: "2-digit", minute: "2-digit"
                          })
                        : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="divider" />

        {/* Failure analysis */}
        {results.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>Failure analysis</div>
            <p style={{ fontSize: 13, marginBottom: 14 }}>Responses where any score is below 0.5.</p>
            {failures.length === 0 ? (
              <div className="success-banner">No failures — all scores are above 0.5.</div>
            ) : (
              failures.map((item, i) => (
                <FailureAccordion key={i} item={item} index={i} />
              ))
            )}
          </div>
        )}

        <div className="divider" style={{ marginTop: 24 }} />

        {/* Clear */}
        {results.length > 0 && (
          <div style={{ marginTop: 20 }}>
            <button className="btn btn-secondary btn-sm" onClick={clearAll}>
              Clear all eval scores
            </button>
          </div>
        )}

      </div>
    </div>
  );
}