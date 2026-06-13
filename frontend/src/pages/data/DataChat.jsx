import { useState, useEffect, useRef } from "react";
import { dataApi } from "../../api/client";
import LoadingDots from "../../components/shared/LoadingDots";
import ChartRenderer from "../../components/data/ChartRenderer";
import MarkdownContent from "../../components/shared/MarkdownContent";

// Persists across tab switches — resets on full page refresh
const clearedFiles = new Set();
const PAGE_SIZE    = 10;

const formatHistory = (history) =>
  history.flatMap((h) => ([
    { role: "user",      content: h.query,  id: `u-${h.id || Math.random()}` },
    { role: "assistant", content: h.answer, id: `a-${h.id || Math.random()}`, chart: (h.chart_data?.datasets?.length || h.chart_data?.values?.length)
  ? (h.chart_data || h.chart)
  : null, sql: h.sql || null, followUps: h.follow_ups || [] },
  ]));

export default function DataChat({ activeFileId, onFileSelect }) {
  const [messages,     setMessages]     = useState([]);
  const [input,        setInput]        = useState("");
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState("");
  const [fileId,       setFileId]       = useState(activeFileId || "");
  const [files,        setFiles]        = useState([]);
  const [sheetNames,   setSheetNames]   = useState([]);
  const [activeSheet,  setActiveSheet]  = useState("");
  const [expandedSql,  setExpandedSql]  = useState({});
  const [offset,       setOffset]       = useState(0);
  const [hasMore,      setHasMore]      = useState(true);
  const [loadingMore,  setLoadingMore]  = useState(false);

  const bottomRef     = useRef(null);
  const scrollRef     = useRef(null);
  const isInitialLoad = useRef(true);

  // Load file list once
  useEffect(() => {
    dataApi.listFiles()
      .then((r) => {
        const all = r.data || [];
        setFiles(all.filter((f) =>
          ["csv", "xlsx", "xls"].includes((f.file_type || "").toLowerCase())
        ));
      })
      .catch(() => {});
  }, []);

  // Sync fileId from parent
  useEffect(() => {
    if (activeFileId) setFileId(activeFileId);
  }, [activeFileId, files]);

  // Initial load when activeFileId changes
  useEffect(() => {
    if (!activeFileId) return;

    setSheetNames([]);
    setActiveSheet("");
    setError("");

    // Load sheet names
    dataApi.getFile(activeFileId)
      .then((r) => {
        const sheets = r.data?.sheet_names || [];
        setSheetNames(sheets);
        if (sheets.length > 1) setActiveSheet(sheets[0]);
      })
      .catch(() => {});

    // Skip history if cleared
    if (clearedFiles.has(activeFileId)) {
      setMessages([]);
      setOffset(0);
      setHasMore(false);
      return;
    }

    // Fetch latest PAGE_SIZE messages
    isInitialLoad.current = true;
    setMessages([]);
    setOffset(0);
    setHasMore(true);

    dataApi.getHistory(activeFileId, PAGE_SIZE, 0)
      .then((res) => {
        const hist = res.data?.history || [];
        setMessages(formatHistory([...hist].reverse()));
        setOffset(PAGE_SIZE);
        setHasMore(hist.length === PAGE_SIZE);
        setTimeout(() => {
          bottomRef.current?.scrollIntoView({ behavior: "instant" });
          isInitialLoad.current = false;
        }, 50);
      })
      .catch(() => { isInitialLoad.current = false; });
  }, [activeFileId]);

  // Scroll handler — load older messages when near top
  const handleScroll = async () => {
    const el = scrollRef.current;
    if (!el || loadingMore || !hasMore || isInitialLoad.current) return;
    if (el.scrollTop > 100) return;

    setLoadingMore(true);
    const prevScrollHeight = el.scrollHeight;

    try {
      const res  = await dataApi.getHistory(activeFileId, PAGE_SIZE, offset);
      const hist = res.data?.history || [];

      if (!hist.length) { setHasMore(false); return; }

      const older = formatHistory(hist);
      setMessages((prev) => [...older, ...prev]);
      setOffset((prev) => prev + PAGE_SIZE);
      setHasMore(hist.length === PAGE_SIZE);

      requestAnimationFrame(() => {
        el.scrollTop = el.scrollHeight - prevScrollHeight;
      });
    } catch {}
    finally { setLoadingMore(false); }
  };

  const handleSelectFile = (id) => {
    setFileId(id);
    setMessages([]);
    setOffset(0);
    setHasMore(true);
    setError("");
    if (onFileSelect) onFileSelect(id);
  };

  const send = async (q) => {
    const question = (q || input).trim();
    if (!question || !fileId || loading) return;
    setInput("");
    setError("");
    setMessages((m) => [...m, { role: "user", content: question, id: `u-${Date.now()}` }]);
    setLoading(true);
    try {
      const res  = await dataApi.askQuestion(fileId, question, activeSheet || undefined);
      const data = res.data;
      setMessages((m) => [
        ...m,
        {
          role:      "assistant",
          content:   data.answer,
          id:        `a-${Date.now()}`,
          chart:     data.chart     || null,
          sql:       data.sql       || null,
          followUps: data.follow_ups || [],
        },
      ]);
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setOffset(0);
    setHasMore(false);
    clearedFiles.add(activeFileId);
  };

  const toggleSql = (id) =>
    setExpandedSql((prev) => ({ ...prev, [id]: !prev[id] }));

  const selectedFile  = files.find((f) => f.file_id === fileId);
  const selectedLabel = selectedFile ? (selectedFile.file_name || fileId) : "No file selected";

  return (
    <div className="chat-layout">
      {/* Header */}
      <div style={{ padding: "14px 28px", borderBottom: "1px solid var(--border)", background: "var(--bg-surface)", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexShrink: 0 }}>
        <div>
          <h2 style={{ marginBottom: 2 }}>Data Chat</h2>
          <p style={{ fontSize: 12 }}>
            {fileId
              ? <>Analysing <span style={{ color: "var(--brand-primary)", fontWeight: 600 }}>{selectedLabel}</span></>
              : "Select a file to begin"}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          {sheetNames.length > 1 && (
            <>
              <label className="field-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Sheet</label>
              <select className="select" style={{ width: "auto", minWidth: 140 }} value={activeSheet} onChange={(e) => setActiveSheet(e.target.value)}>
                {sheetNames.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </>
          )}
          <label className="field-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Active File</label>
          <select
            className="select"
            style={{ width: "auto", minWidth: 220 }}
            value={activeFileId || fileId || ""}
            onChange={(e) => handleSelectFile(e.target.value)}
          >
            <option value="">Select a file…</option>
            {files.map((f) => (
              <option key={f.file_id} value={f.file_id}>{f.file_name}</option>
            ))}
          </select>
          {messages.length > 0 && (
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearChat}>
              Clear Chat
            </button>
          )}
        </div>
      </div>

      {/* Scrollable messages area */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="chat-messages"
      >
        {/* Loading older messages indicator */}
        {loadingMore && (
          <div style={{ textAlign: "center", padding: "10px 0", fontSize: 12, color: "var(--text-muted)" }}>
            Loading older messages…
          </div>
        )}

        {/* Beginning of conversation */}
        {!hasMore && messages.length > 0 && (
          <div style={{ textAlign: "center", padding: "10px 0", fontSize: 12, color: "var(--text-disabled)" }}>
            Beginning of conversation
          </div>
        )}

        {!fileId && (
          <div className="empty-state">
            <div className="empty-state-title">No file selected</div>
            <p>Choose a CSV or Excel file from the dropdown above.</p>
          </div>
        )}

        {fileId && messages.length === 0 && !loading && (
          <div className="empty-state">
            <div className="empty-state-title">Start a conversation</div>
            <p>Ask about trends, totals, comparisons — or say "show me a chart of X by Y".</p>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`message ${m.role}`}>
            <div className="message-bubble">
              {m.role === "assistant"
                ? <MarkdownContent content={m.content} />
                : m.content}
            </div>

            {m.chart && <ChartRenderer chart={m.chart} height={300} />}

            {m.sql && (
              <div style={{ marginTop: 10 }}>
                <button
                  type="button"
                  onClick={() => toggleSql(m.id)}
                  style={{ background: "none", border: "none", cursor: "pointer", fontSize: 11, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-muted)", padding: 0, display: "flex", alignItems: "center", gap: 5 }}
                >
                  <span style={{ fontSize: 10 }}>{expandedSql[m.id] ? "▼" : "▶"}</span>
                  Generated SQL
                </button>
                {expandedSql[m.id] && (
                  <pre style={{ marginTop: 6, background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius)", padding: "10px 14px", fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--info)", overflowX: "auto" }}>
                    {m.sql}
                  </pre>
                )}
              </div>
            )}

            {m.followUps?.length > 0 && (
              <div className="followup-list">
                {m.followUps.map((f, fi) => (
                  <button key={fi} type="button" className="followup-chip" onClick={() => send(f)} disabled={loading}>
                    {f}
                  </button>
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
          type="button"
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