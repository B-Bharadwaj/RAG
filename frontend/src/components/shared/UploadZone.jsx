import { useState, useRef } from "react";

export default function UploadZone({ accept, onFile, label, hint }) {
  const [drag, setDrag] = useState(false);
  const ref = useRef();

  const handle = (file) => {
    if (file) onFile(file);
  };

  return (
    <div
      className={`upload-zone${drag ? " drag-over" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); handle(e.dataTransfer.files[0]); }}
      onClick={() => ref.current.click()}
    >
      <input
        ref={ref}
        type="file"
        accept={accept}
        style={{ display: "none" }}
        onChange={(e) => handle(e.target.files[0])}
      />
      <div className="upload-icon">+</div>
      <div className="upload-title">{label || "Drop file here or click to browse"}</div>
      <div className="upload-hint">{hint || accept}</div>
    </div>
  );
}