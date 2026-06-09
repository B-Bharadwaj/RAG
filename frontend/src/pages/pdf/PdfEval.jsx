import { useState, useEffect } from "react";
import { pdfApi } from "../../api/client";

function ScoreCell({ score }) {
  if (score == null) return <span style={{ color: "var(--text-disabled)" }}>—</span>;
  const pct   = score <= 1 ? score : score / 100;
  const color = pct >= 0.7 ? "var(--success)" : pct >= 0.4 ? "var(--warning)" : "var(--danger)";
  return <span style={{ fontFamily: "var(--font-mono)", color, fontWeight: 600 }}>{pct.toFixed(4)}</span>;
}

function FailureAccordion({ item, index }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius)", overflow: "hidden", marginBottom: 8 }}>
      <div
        onClick={() => setOpen(!open)}
        style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 16px", cursor: "pointer", background: "var(--bg-elevated)", userSelect: "none" }}
      >
        <span style={{ color: "var(--text-muted)", fontSize: 13, display: "inline-block", transform: open ? "rotate(90deg)" : "none", transition: "transform 0.2s" }}>›</span>
        <span style={{ fontSize: 13, fontWeight: 500 }}>{item.query || `Query ${index + 1}`}</span>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {[["F", item.faithfulness], ["R", item.relevancy], ["C", item.context_recall]].map(([k, v]) =>
            v != null ? (
              <span key={k} style={{ fontSize: 11, fontFamily: "var(--font-mono)", color: v < 0.3 ? "var(--danger)" : "var(--success)" }}>
                {k}:{v.toFixed(2)}
              </span>
            ) : null
          )}
        </div>
      </div>
      {open && (
        <div style={{ padding: "14px 16px", borderTop: "1px solid var(--border)", background: "var(--bg-surface)" }}>
          {item.reasoning && <div style={{ marginBottom: 10 }}><div className="text-sm text-muted mb-8">Reasoning</div><p style={{ fontSize: 13, lineHeight: 1.7 }}>{item.reasoning}</p></div>}
          {item.answer    && <div style={{ marginBottom: 10 }}><div className="text-sm text-muted mb-8">Answer</div><p style={{ fontSize: 13, lineHeight: 1.7, color: "var(--text-secondary)" }}>{item.answer}</p></div>}
          {item.scope     && <div><div className="text-sm text-muted mb-8">Scope</div><span className="badge badge-neutral text-mono" style={{ fontSize: 11 }}>{item.scope}</span></div>}
        </div>
      )}
    </div>
  );
}

export default function PdfEval() {
  const [scores,      setScores]      = useState([]);
  const [evalSummary, setEvalSummary] = useState(null);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState("");
  const [scoring,     setScoring]     = useState(false);
  const [scoreMsg,    setScoreMsg]    = useState("");
  const [limit,       setLimit]       = useState(10);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await pdfApi.getEvalResults();
      setScores(Array.isArray(res.data?.scores) ? res.data.scores : []);
      if (res.data?.summary) setEvalSummary(res.data.summary);
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
    await pdfApi.clearEvalResults().catch(() => {});
    setScores([]);
    setEvalSummary(null);
    setScoreMsg("");
  };

  const avgFaith   = evalSummary?.avg_faithfulness  ?? null;
  const avgRel     = evalSummary?.avg_relevancy      ?? null;
  const avgContext = evalSummary?.avg_context_recall ?? null;
  const total      = evalSummary?.total              ?? scores.length;

  const failures = scores.filter((r) =>
    (r.faithfulness   != null && r.faithfulness   < 0.3) ||
    (r.relevancy      != null && r.relevancy      < 0.3) ||
    (r.context_recall != null && r.context_recall < 0.3)
  );

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>RAG Evaluation Dashboard</h1>
            <p>Judge LLM scores each response across Faithfulness, Answer Relevancy, and Context Recall.</p>
          </div>
          <div className="page-header-actions">
            <button className="btn btn-secondary btn-sm" onClick={load}>Refresh</button>
            {scores.length > 0 && (
              <button className="btn btn-danger btn-sm" onClick={clearAll}>Clear Results</button>
            )}
          </div>
        </div>

        {error    && <div className="error-banner mb-16">{error}</div>}
        {scoreMsg && <div className="success-banner mb-16">{scoreMsg}</div>}

        {/* Score Now */}
        <div className="card mb-24">
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Queries to score (most recent un-scored)</div>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <input
              type="range" min={1} max={20} value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              style={{ flex: 1, accentColor: "var(--accent)" }}
            />
            <span className="text-mono" style={{ minWidth: 24, textAlign: "center", fontWeight: 600 }}>{limit}</span>
            <button className="btn btn-primary" onClick={scoreNow} disabled={scoring} style={{ minWidth: 140 }}>
              {scoring ? <><span className="spinner" /> Scoring…</> : "Score Now"}
            </button>
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
            { label: "Total Scored",       value: total },
          ].map((k) => (
            <div key={k.label} className="kpi-card">
              <div className="kpi-label">{k.label}</div>
              <div className="kpi-value" style={{ fontSize: 22 }}>{k.value}</div>
            </div>
          ))}
        </div>

        <div className="divider" />

        {/* Score history */}
        <div style={{ fontWeight: 600, fontSize: 15, margin: "20px 0 12px" }}>Score history</div>
        {loading ? (
          <div className="empty-state"><div className="spinner" style={{ margin: "0 auto" }} /></div>
        ) : scores.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-title">No scores yet</div>
            <p>Click "Score Now" to evaluate recent queries from the database.</p>
          </div>
        ) : (
          <div className="table-wrap mb-24" style={{ overflowX: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th style={{ width: "18%", minWidth: 120 }}>Query</th>
                  <th style={{ width: "9%",  minWidth: 90  }}>Faithfulness</th>
                  <th style={{ width: "9%",  minWidth: 80  }}>Relevancy</th>
                  <th style={{ width: "9%",  minWidth: 90, whiteSpace: "nowrap" }}>Context Recall</th>
                  <th style={{ width: "32%", minWidth: 160 }}>Reasoning</th>
                  <th style={{ width: "12%", minWidth: 80  }}>Scope</th>
                  <th style={{ width: "11%", minWidth: 90, whiteSpace: "nowrap" }}>Scored At</th>
                </tr>
              </thead>
              <tbody>
                {scores.map((r, i) => (
                  <tr key={i}>
                    <td style={{ maxWidth: 160 }}>
                      <div className="truncate" style={{ fontWeight: 500, color: "var(--text-primary)" }} title={r.query}>{r.query || "—"}</div>
                    </td>
                    <td><ScoreCell score={r.faithfulness} /></td>
                    <td><ScoreCell score={r.relevancy ?? r.relevance} /></td>
                    <td><ScoreCell score={r.context_recall} /></td>
                    <td style={{ maxWidth: 300 }}><div className="truncate text-sm" title={r.reasoning}>{r.reasoning || "—"}</div></td>
                    <td className="text-mono text-sm" style={{ maxWidth: 100, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={r.scope}>
                      {r.scope === "All PDFs" || !r.scope ? "All PDFs" : r.scope.slice(0, 8) + "…"}
                    </td>
                    <td className="text-sm text-muted" style={{ whiteSpace: "nowrap" }}>
                      {r.scored_at ? new Date(r.scored_at).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Failure analysis */}
        {scores.length > 0 && (
          <>
            <div className="divider" />
            <div style={{ marginTop: 20 }}>
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>Failure analysis</div>
              <p style={{ fontSize: 13, marginBottom: 14 }}>Responses where any score is below 0.3.</p>
              {failures.length === 0
                ? <div className="success-banner">No failures — all scores are above 0.3.</div>
                : failures.map((item, i) => <FailureAccordion key={i} item={item} index={i} />)
              }
            </div>
            <div style={{ marginTop: 24 }}>
              <button className="btn btn-secondary btn-sm" onClick={clearAll}>Clear all eval scores</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}