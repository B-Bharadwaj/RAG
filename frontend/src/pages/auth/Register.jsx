import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { GoogleLogin } from "@react-oauth/google";
import { useAuth } from "../../context/AuthContext";
import { authApi } from "../../api/client";

export default function Register() {
  const { login }    = useAuth();
  const navigate     = useNavigate();
  const [form, setForm]   = useState({ name: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const res = await authApi.register(form.name, form.email, form.password);
      login(res.data.access_token, res.data.user);
      navigate("/pdf/upload", { replace: true });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async (credentialResponse) => {
    setError("");
    try {
      const res = await authApi.googleLogin(credentialResponse.credential);
      login(res.data.access_token, res.data.user);
      navigate("/pdf/upload", { replace: true });
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div style={{
      minHeight: "100vh", background: "var(--bg-base)",
      display: "flex", alignItems: "center", justifyContent: "center", padding: 24,
    }}>
      <div style={{
        width: "100%", maxWidth: 420,
        background: "var(--bg-surface)", border: "1px solid var(--border)",
        borderRadius: "var(--radius-xl)", padding: "40px 36px",
        boxShadow: "var(--shadow-lg)",
      }}>
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div style={{ fontSize: 13, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-primary)", marginBottom: 6 }}>
            RAGBOT
          </div>
          <h1 style={{ fontSize: 22, marginBottom: 6 }}>Create an account</h1>
          <p style={{ fontSize: 13 }}>Get started with RAGBOT</p>
        </div>

        {error && <div className="error-banner mb-16">{error}</div>}

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div>
            <label className="field-label">Full Name</label>
            <input
              className="input"
              type="text"
              placeholder="John Doe"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="field-label">Email</label>
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              required
            />
          </div>
          <div>
            <label className="field-label">Password</label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              required
            />
          </div>
          <button
            type="submit"
            className="btn btn-primary w-full"
            style={{ marginTop: 4 }}
            disabled={loading}
          >
            {loading ? <><span className="spinner" /> Creating account…</> : "Create Account"}
          </button>
        </form>

        <div style={{ display: "flex", alignItems: "center", gap: 12, margin: "20px 0" }}>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
          <span style={{ fontSize: 12, color: "var(--text-muted)" }}>or</span>
          <div style={{ flex: 1, height: 1, background: "var(--border)" }} />
        </div>

        <div style={{ display: "flex", justifyContent: "center" }}>
          <GoogleLogin
            onSuccess={handleGoogle}
            onError={() => setError("Google sign-in failed")}
            theme="outline"
            shape="rectangular"
            width="348"
          />
        </div>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: 13 }}>
          Already have an account?{" "}
          <Link to="/login" style={{ color: "var(--accent)", fontWeight: 600 }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}