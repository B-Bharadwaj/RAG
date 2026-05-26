import { useState } from "react";
import { pdfApi } from "../../api/client";
import UploadZone from "../../components/shared/UploadZone";

export default function PdfUpload() {
  const [file, setFile] = useState(null);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState(null); // "uploading"|"done"|"error"
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const handleFile = (f) => {
    setFile(f);
    setStatus(null);
    setResult(null);
    setError("");
    setProgress(0);
  };

  const upload = async () => {
    if (!file) return;
    setStatus("uploading");
    setError("");
    try {
      const res = await pdfApi.uploadDocument(file, setProgress);
      setResult(res.data);
      setStatus("done");
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  };

  return (
    <div className="page-content">
      <div className="page-inner">
        <div className="page-header">
          <div className="page-header-left">
            <h1>Upload PDF</h1>
            <p>Index a research paper into the RAG pipeline</p>
          </div>
        </div>

        <UploadZone
          accept=".pdf"
          onFile={handleFile}
          label="Drop your PDF here or click to browse"
          hint="Only PDF files are supported"
        />

        {file && (
          <div className="card mt-16">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600, marginBottom: 3 }}>{file.name}</div>
                <div className="text-sm text-muted">
                  {(file.size / 1024 / 1024).toFixed(2)} MB
                </div>
              </div>
              <button
                className="btn btn-primary"
                onClick={upload}
                disabled={status === "uploading" || status === "done"}
              >
                {status === "uploading" ? (
                  <><span className="spinner" /> Uploading…</>
                ) : status === "done" ? "Uploaded" : "Upload & Index"}
              </button>
            </div>

            {status === "uploading" && (
              <div className="progress-bar mt-12">
                <div className="progress-fill" style={{ width: `${progress}%` }} />
              </div>
            )}
          </div>
        )}

        {error && <div className="error-banner mt-16">{error}</div>}

        {status === "done" && result && (
          <div className="success-banner mt-16">
            Document indexed successfully.
            {result.doc_id && (
              <span className="text-mono" style={{ marginLeft: 8 }}>
                ID: {result.doc_id}
              </span>
            )}
            {result.chunks && (
              <span style={{ marginLeft: 8 }}>{result.chunks} chunks created.</span>
            )}
          </div>
        )}

        <div className="card mt-24">
          <div className="card-title">How it works</div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginTop: 8 }}>
            {["PDF is parsed and chunked into passages",
              "Each chunk is embedded and stored in the vector index",
              "Questions are answered using semantic retrieval + LLM"
            ].map((step, i) => (
              <div key={i} style={{ display: "flex", gap: 12 }}>
                <div style={{ fontSize: 11, fontFamily: "var(--font-mono)", background: "var(--bg-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "3px 8px", height: "fit-content", color: "var(--text-muted)", flexShrink: 0 }}>
                  {String(i + 1).padStart(2, "0")}
                </div>
                <p style={{ fontSize: 13 }}>{step}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}