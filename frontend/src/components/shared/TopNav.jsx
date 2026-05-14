
import { useNavigate, useLocation } from "react-router-dom";

export default function TopNav({ mode, onModeChange }) {
  return (
    <nav className="topnav">
      <span className="topnav-brand">
        <span></span>RAGBOT
      </span>
      <div className="mode-toggle">
        <button
          className={`mode-btn ${mode === "pdf" ? "active" : ""}`}
          onClick={() => onModeChange("pdf")}
        >
          PDF Mode
        </button>
        <button
          className={`mode-btn ${mode === "data" ? "active" : ""}`}
          onClick={() => onModeChange("data")}
        >
          Data Mode
        </button>
      </div>
    </nav>
  );
}
