import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownContent({ content }) {
  if (!content) return null;

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Bold — used for **filename.pdf** headers
        strong: ({ children }) => (
          <strong style={{
            color: "var(--brand-primary)",
            fontWeight: 700,
            fontSize: "14px",
            display: "block",
            marginTop: "18px",
            marginBottom: "6px",
            letterSpacing: "0.01em",
          }}>
            {children}
          </strong>
        ),
        // Paragraphs
        p: ({ children }) => (
          <p style={{
            color: "var(--text-secondary)",
            fontSize: "13.5px",
            lineHeight: 1.75,
            marginBottom: "12px",
          }}>
            {children}
          </p>
        ),
        // Headings
        h1: ({ children }) => (
          <h1 style={{ color: "var(--text-primary)", marginBottom: 10, marginTop: 20 }}>{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 style={{ color: "var(--text-primary)", marginBottom: 8, marginTop: 18 }}>{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 style={{ color: "var(--text-primary)", marginBottom: 6, marginTop: 14 }}>{children}</h3>
        ),
        // Lists
        ul: ({ children }) => (
          <ul style={{ paddingLeft: 20, marginBottom: 12, color: "var(--text-secondary)", fontSize: 13.5 }}>
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol style={{ paddingLeft: 20, marginBottom: 12, color: "var(--text-secondary)", fontSize: 13.5 }}>
            {children}
          </ol>
        ),
        li: ({ children }) => (
          <li style={{ marginBottom: 4, lineHeight: 1.65 }}>{children}</li>
        ),
        // Inline code
        code: ({ inline, children }) =>
          inline ? (
            <code style={{
              background: "var(--bg-elevated)",
              padding: "2px 6px",
              borderRadius: 3,
              fontSize: 12,
              fontFamily: "var(--font-mono)",
              color: "var(--brand-primary)",
            }}>
              {children}
            </code>
          ) : (
            <pre style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius)",
              padding: "14px 16px",
              overflowX: "auto",
              marginBottom: 12,
            }}>
              <code style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                color: "var(--text-secondary)",
              }}>
                {children}
              </code>
            </pre>
          ),
        // Blockquote — used for CONFIDENCE lines
        blockquote: ({ children }) => (
          <blockquote style={{
            borderLeft: "3px solid var(--brand-secondary)",
            paddingLeft: 14,
            color: "var(--text-muted)",
            fontStyle: "italic",
            margin: "10px 0",
          }}>
            {children}
          </blockquote>
        ),
        // Horizontal rule — section separator
        hr: () => (
          <hr style={{ border: "none", borderTop: "1px solid var(--border)", margin: "16px 0" }} />
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}