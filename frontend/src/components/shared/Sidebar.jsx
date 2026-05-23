import { NavLink } from "react-router-dom";

const PDF_LINKS = [
  { to: "/pdf/upload", label: "Upload" },
  { to: "/pdf/chat", label: "Chat" },
  { to: "/pdf/manage", label: "Manage Documents" },
  { to: "/pdf/report", label: "Reports" },
  { to: "/pdf/compare", label: "Compare Papers" },
  { to: "/pdf/eval", label: "Evaluation" },
];

const DATA_LINKS = [
  { to: "/data/upload", label: "Upload" },
  { to: "/data/chat", label: "Chat" },
  { to: "/data/manage", label: "Manage Files" },
  { to: "/data/report", label: "Reports" },
  { to: "/data/visualize", label: "Visualize" },
  { to: "/data/querylog", label: "Query Log" },
];

export default function Sidebar({ mode }) {
  const links = mode === "pdf" ? PDF_LINKS : DATA_LINKS;

  return (
    <aside className="sidebar">
      <div className="sidebar-section">
        <div className="sidebar-label">{mode === "pdf" ? "PDF Pipeline" : "BI Pipeline"}</div>
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            <span className="sidebar-dot" />
            {l.label}
          </NavLink>
        ))}
      </div>
    </aside>
  );
}