import { useState, useEffect, useRef } from "react";
import { pdfApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";
import MarkdownContent from "../../components/shared/MarkdownContent";

function SourcesDropdown({ sources }) {
  const [open, setOpen] = useState(false);
  if (!sources?.length) return null;

  return (
    <div style={{ marginTop: 10 }}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        style={{
          background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius)",
          cursor: "pointer", fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
          color: "var(--text-muted)", padding: "4px 10px", display: "inline-flex",
          alignItems: "center", gap: 6, transition: "all var(--transition)",
        }}
      >
        <span style={{ fontSize: 10 }}>{open ? "▼" : "▶"}</span>
        View Sources ({sources.length})
      </button>

      {open && (
        <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          {sources.map((s, i) => (
            <div key={i} style={{
              background: "var(--bg-elevated)", border: "1px solid var(--border)",
              borderRadius: "var(--radius)", padding: "10px 14px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <span style={{ fontWeight: 600, fontSize: 12, color: "var(--brand-primary)" }}>
                  {s.pdf || s.filename || s.source || s.doc_id || `Source ${i + 1}`}
                </span>
                {(s.page || s.page_number) && (
                  <span className="badge badge-neutral" style={{ fontSize: 10 }}>
                    p.{s.page || s.page_number}
                  </span>
                )}
                {s.score != null && (
                  <span className="badge badge-info" style={{ fontSize: 10 }}>
                    {Math.round(s.score * 100)}%
                  </span>
                )}
              </div>
              {(s.preview || s.text) && (
                <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0, lineHeight: 1.6 }}>
                  {(s.preview || s.text || "").slice(0, 150)}
                  {(s.preview || s.text || "").length > 150 ? "…" : ""}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function PdfChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState("all");
  const bottomRef = useRef();

  useEffect(() => {
    pdfApi.listDocuments()
      .then((r) => setDocuments(r.data?.documents || r.data || []))
      .catch(() => { });

    pdfApi.getHistory()
      .then((r) => {
        const hist = r.data?.history || r.data || [];
        if (hist.length) {
          const msgs = hist.flatMap((h) => [
            { role: "user", content: h.query || h.question },
            { role: "assistant", content: h.answer, sources: h.sources || [] },
          ]);
          setMessages(msgs);
        }
      })
      .catch(() => { });
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const send = async () => {
    const q = input.trim();
    if (!q || loading) return;
    setInput("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: q }]);
    setLoading(true);
    try {
      const docId = selectedDocId === "all" ? null : selectedDocId;
      const res = await pdfApi.chat(q, docId);
      const data = res.data;
      setMessages((m) => [
        ...m,
        { role: "assistant", content: data.answer, sources: data.sources || [] },
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  // Clear memory — only resets local state, no confirm popup
  const clearMemory = () => {
    pdfApi.clearMemory().catch(() => { });
    pdfApi.clearHistory().catch(() => { });
    setMessages([]);
    setError("");
  };

  const selectedLabel =
    selectedDocId === "all"
      ? "All Documents"
      : (documents.find((d) => (d.id || d.doc_id) === selectedDocId)?.filename || "Selected PDF")
        .replace(/\.pdf$/i, "");

  return (
    <div className="chat-layout">
      {/* Header */}
      <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--border)", background: "var(--bg-surface)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexShrink: 0 }}>
        <div>
          <h2 style={{ marginBottom: 2 }}>Research Chat</h2>
          <p style={{ fontSize: 12 }}>
            Searching across{" "}
            <span style={{ color: "var(--brand-primary)", fontWeight: 600 }}>{selectedLabel}</span>
          </p>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <label className="field-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Search in</label>
          <select
            className="select"
            style={{ width: "auto", minWidth: 220 }}
            value={selectedDocId}
            onChange={(e) => setSelectedDocId(e.target.value)}
          >
            <option value="all">All Documents</option>
            {documents.map((d) => {
              const id = d.id || d.doc_id;
              const name = (d.filename || d.title || id).replace(/\.pdf$/i, "");
              return <option key={id} value={id}>{name}</option>;
            })}
          </select>
          <button type="button" className="btn btn-ghost btn-sm" onClick={clearMemory}>
            Clear Memory
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-state-title">No conversation yet</div>
            <p>{documents.length === 0
              ? "Upload PDFs first, then come back to chat."
              : "Select a document or search all, then ask a question."}
            </p>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-bubble">
              {m.role === "assistant"
                ? <MarkdownContent content={m.content} />
                : m.content}
            </div>
            {m.role === "assistant" && (
              <SourcesDropdown sources={m.sources} />
            )}
            <div className="message-meta">{m.role === "user" ? "You" : "Assistant"}</div>
          </div>
        ))}

        {loading && (
          <div className="message assistant">
            <div className="message-bubble"><LoadingDots /></div>
          </div>
        )}
        {error && <div className="error-banner">{error}</div>}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-bar">
        <textarea
          className="textarea"
          placeholder={documents.length === 0 ? "Upload PDFs first…" : `Ask a question about ${selectedLabel}…`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          rows={1}
        />
        <button type="button" className="btn btn-primary" onClick={send} disabled={loading || !input.trim()}>
          {loading ? <span className="spinner" /> : "Send"}
        </button>
      </div>
    </div>
  );
}