import { useState, useEffect, useRef } from "react";
import { pdfApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";
import MarkdownContent from "../../components/shared/MarkdownContent";

export default function PdfChat() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState("all");
  const bottomRef = useRef();

  // Fetch documents + history on mount
  useEffect(() => {
    pdfApi.listDocuments()
      .then((r) => setDocuments(r.data?.documents || r.data || []))
      .catch(() => {});

    pdfApi.getHistory()
      .then((r) => {
        const hist = r.data?.history || r.data || [];
        if (hist.length) {
          const msgs = hist.flatMap((h) => [
            { role: "user",      content: h.query || h.question },
            { role: "assistant", content: h.answer, sources: h.sources || [] },
          ]);
          setMessages(msgs);
        }
      })
      .catch(() => {});
  }, []);

  // Scroll to bottom on new messages
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

  // Clear Memory = wipe LLM memory + wipe SQLite history + wipe UI
  const clearMemory = () => {
    pdfApi.clearMemory().catch(() => {});
    pdfApi.clearHistory().catch(() => {});
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
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
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
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={clearMemory}
          >
            Clear Memory
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-state-title">No conversation yet</div>
            <p>
              {documents.length === 0
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
            {m.role === "assistant" && m.sources?.length > 0 && (
              <div className="sources-list">
                {m.sources.map((s, si) => (
                  <div key={si} className="source-chip">
                    <span className="source-chip-score">
                      {s.score ? `${Math.round(s.score * 100)}%` : "src"}
                    </span>
                    <span className="truncate" style={{ maxWidth: 300 }}>
                      {s.filename || s.source || s.doc_id || `Source ${si + 1}`}
                    </span>
                    {s.page && <span style={{ color: "var(--text-disabled)" }}>p.{s.page}</span>}
                  </div>
                ))}
              </div>
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

        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="chat-input-bar">
        <textarea
          className="textarea"
          placeholder={documents.length === 0 ? "Upload PDFs first…" : `Ask a question about ${selectedLabel}…`}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          rows={1}
        />
        <button
          type="button"
          className="btn btn-primary"
          onClick={send}
          disabled={loading || !input.trim()}
        >
          {loading ? <span className="spinner" /> : "Send"}
        </button>
      </div>
    </div>
  );
}
