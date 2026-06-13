import { NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const PDF_LINKS = [
  { to: "/pdf/upload",  label: "Upload" },
  { to: "/pdf/chat",    label: "Chat" },
  { to: "/pdf/manage",  label: "Manage Documents" },
  { to: "/pdf/report",  label: "Reports" },
  { to: "/pdf/compare", label: "Compare Papers" },
  { to: "/pdf/eval",    label: "Evaluation" },
];

const DATA_LINKS = [
  { to: "/data/upload",    label: "Upload" },
  { to: "/data/chat",      label: "Chat" },
  { to: "/data/manage",    label: "Manage Files" },
  { to: "/data/report",    label: "Reports" },
  { to: "/data/visualize", label: "Visualize" },
  { to: "/data/querylog",  label: "Query Log" },
];

export default function Sidebar({ mode }) {
  const { user, logout } = useAuth();
  const links = mode === "pdf" ? PDF_LINKS : DATA_LINKS;

  return (
    <aside className="sidebar" style={{ display: "flex", flexDirection: "column" }}>
      <div className="sidebar-section" style={{ flex: 1 }}>
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

      {/* User info + logout at bottom */}
      {user && (
        <div style={{
          padding: "14px 16px",
          borderTop: "1px solid var(--border)",
          marginTop: "auto",
        }}>
          {/* Avatar + name */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            {user.avatar ? (
              <img
                src={user.avatar}
                alt={user.name}
                style={{ width: 30, height: 30, borderRadius: "50%", objectFit: "cover", flexShrink: 0 }}
              />
            ) : (
              <div style={{
                width: 30, height: 30, borderRadius: "50%",
                background: "var(--accent-dim)", border: "1px solid var(--border)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 12, fontWeight: 700, color: "var(--accent)", flexShrink: 0,
              }}>
                {(user.name || user.email || "U")[0].toUpperCase()}
              </div>
            )}
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontSize: 12, fontWeight: 600, color: "var(--text-primary)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {user.name || "User"}
              </div>
              <div style={{
                fontSize: 11, color: "var(--text-muted)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }}>
                {user.email}
              </div>
            </div>
          </div>

          {/* Logout button */}
          <button
            type="button"
            onClick={logout}
            className="btn btn-ghost btn-sm"
            style={{ width: "100%", justifyContent: "center", fontSize: 12 }}
          >
            Sign Out
          </button>
        </div>
      )}
    </aside>
  );
}