import { useState, useEffect } from "react";
import { dataApi } from "../../api/client";

export default function FileSelector({ selectedId, onSelect }) {
  const [files, setFiles] = useState([]);

  useEffect(() => {
    // FileInfoResponse fields: file_id, file_name, file_type, row_count, col_count
    dataApi.listFiles()
      .then((r) => setFiles(r.data || []))
      .catch(() => {});
  }, []);

  if (!files.length) return null;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <label className="field-label" style={{ margin: 0, whiteSpace: "nowrap" }}>Active File</label>
      <select
        className="select"
        style={{ width: "auto", minWidth: 200 }}
        value={selectedId || ""}
        onChange={(e) => onSelect(e.target.value)}
      >
        <option value="">Select a file…</option>
        {files.map((f) => (
          <option key={f.file_id} value={f.file_id}>
            {f.file_name}
          </option>
        ))}
      </select>
    </div>
  );
}