import { useState, useEffect, useRef } from "react";
import { dataApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";
import MarkdownContent from "../../components/shared/MarkdownContent";
import ChartRenderer from "../../components/data/ChartRenderer";

export default function DataChat({ activeFileId, onFileSelect }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [fileId, setFileId] = useState(activeFileId || "");
  const [files, setFiles] = useState([]);
  const bottomRef = useRef();

  // Load all uploaded files for the dropdown
  useEffect(() => {
    dataApi.listFiles()
      .then((r) => {
        const all = r.data || [];
        setFiles(all.filter((f) => ['csv','xlsx','xls'].includes((f.file_type||'').toLowerCase())));
      })
      .catch(() => {});
  }, []);

  // Sync active file from parent
  useEffect(() => {
    if (activeFileId) setFileId(activeFileId);
  }, [activeFileId]);

  // Load history when file changes
  useEffect(() => {
    if (!fileId) return;
    setMessages([]);
    dataApi.getHistory(fileId)
      .then((r) => {
        const hist = r.data?.history || r.data || [];
        if (hist.length) {
          const msgs = hist.flatMap((h) => [
            { role: "user", content: h.query },
            { role: "assistant", content: h.answer, followUps: h.follow_ups || [], chart: h.chart },
          ]);
          setMessages(msgs);
        }
      })
      .catch(() => {});
  }, [fileId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSelectFile = (id) => {
    setFileId(id);
    setMessages([]);
    setError("");
    if (onFileSelect) onFileSelect(id);
  };

  const send = async (q) => {
    const question = (q || input).trim();
    if (!question || !fileId || loading) return;
    setInput("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: question }]);
    setLoading(true);
    try {
      const res = await dataApi.askQuestion(fileId, question);
      const data = res.data;
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: data.answer,
          followUps: data.follow_ups || [],
          chart: data.chart || null,
          sql: data.sql || null,
        },
      ]);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const selectedFile = files.find((f) => (f.file_id) === fileId);
  const selectedLabel = selectedFile
    ? (selectedFile.file_name || fileId)
    : "No file selected";

  return (
    <div className="chat-layout">
      {/* Header */}
      <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--border)", background: "var(--bg-surface)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div>
          <h2 style={{ marginBottom: 2 }}>Data Chat</h2>
          <p style={{ fontSize: 12 }}>
            {fileId
              ? <>Analysing <span style={{ color: "var(--accent)", fontWeight: 600 }}>{selectedLabel}</span></>
              : "Select a file to begin"}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label className="field-label" style={{ margin: 0, whiteSpace: "nowrap" }}>
            Active File
          </label>
          <select
            className="select"
            style={{ width: "auto", minWidth: 220 }}
            value={fileId}
            onChange={(e) => handleSelectFile(e.target.value)}
          >
            <option value="">Select a file…</option>
            {files.map((f) => {
              const id = f.file_id;
              const name = f.file_name;
              return (
                <option key={id} value={id}>{name}</option>
              );
            })}
          </select>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages">
        {!fileId && (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Choose a CSV or Excel file from the dropdown above, or upload one first.</p>
          </div>
        )}
        {fileId && messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-state-title">Start a conversation</div>
            <p>Ask about trends, aggregations, comparisons, or request a chart.</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`message ${m.role}`}>
            <div className="message-bubble">
              {m.role === "assistant"
                ? <MarkdownContent content={m.content} />
                : m.content}
            </div>
            {m.chart && <ChartRenderer chartData={m.chart} />}
            {m.sql && (
              <div style={{ marginTop: 10 }}>
                <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--text-disabled)', marginBottom: 5 }}>Generated SQL</div>
                <pre style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 'var(--radius)', padding: '10px 14px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--info)', overflowX: 'auto', margin: 0 }}>
                  {m.sql}
                </pre>
              </div>
            )}
            {m.followUps?.length > 0 && (
              <div className="followup-list">
                {m.followUps.map((f, fi) => (
                  <button
                    key={fi}
                    className="followup-chip"
                    onClick={() => send(f)}
                    disabled={loading}
                  >
                    {f}
                  </button>
                ))}
              </div>
            )}
            <div className="message-meta">
              {m.role === "user" ? "You" : "Assistant"}
            </div>
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
          placeholder={fileId ? `Ask a question about ${selectedLabel}…` : "Select a file first…"}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
          }}
          disabled={!fileId}
          rows={1}
        />
        <button
          className="btn btn-primary"
          onClick={() => send()}
          disabled={loading || !input.trim() || !fileId}
        >
          {loading ? <span className="spinner" /> : "Send"}
        </button>
      </div>
    </div>
  );
}