import { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";
import { GoogleOAuthProvider } from "@react-oauth/google";

import "./styles/global.css";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/auth/ProtectedRoute";
import TopNav from "./components/shared/TopNav";
import Sidebar from "./components/shared/Sidebar";
import { dataApi } from "./api/client";

// Auth pages
import Login    from "./pages/auth/Login";
import Register from "./pages/auth/Register";

// PDF pages
import PdfChat    from "./pages/pdf/PdfChat";
import PdfUpload  from "./pages/pdf/PdfUpload";
import PdfManage  from "./pages/pdf/PdfManage";
import PdfCompare from "./pages/pdf/PdfCompare";
import PdfReport  from "./pages/pdf/PdfReport";
import PdfEval    from "./pages/pdf/PdfEval";

// Data pages
import DataUpload    from "./pages/data/DataUpload";
import DataChat      from "./pages/data/DataChat";
import DataManage    from "./pages/data/DataManage";
import DataVisualize from "./pages/data/DataVisualize";
import DataReport    from "./pages/data/DataReport";
import DataQueryLog  from "./pages/data/DataQueryLog";

const STORAGE_KEY = "ragbot_active_file_id";
const GOOGLE_CLIENT_ID = process.env.REACT_APP_GOOGLE_CLIENT_ID || "86907060508-omauedqr71g6449f6j246tpm3f34nmdv.apps.googleusercontent.com";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();

  const [activeDataFileId, setActiveDataFileId] = useState(
    () => localStorage.getItem(STORAGE_KEY) || ""
  );
  const [compareHistory, setCompareHistory] = useState([]);

  useEffect(() => {
    dataApi.listFiles()
      .then((r) => {
        const all = (r.data || []).filter((f) =>
          ["csv", "xlsx", "xls"].includes((f.file_type || "").toLowerCase())
        );
        if (!all.length) {
          setActiveDataFileId("");
          localStorage.removeItem(STORAGE_KEY);
          return;
        }
        const stored      = localStorage.getItem(STORAGE_KEY);
        const stillExists = stored && all.find((f) => f.file_id === stored);
        if (stillExists) {
          setActiveDataFileId(stored);
        } else {
          const latest = all[all.length - 1];
          setActiveDataFileId(latest.file_id);
          localStorage.setItem(STORAGE_KEY, latest.file_id);
        }
      })
      .catch(() => {});
  }, []);

  const handleFileSelect = (id) => {
    setActiveDataFileId(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  const mode = location.pathname.startsWith("/data") ? "data" : "pdf";

  const handleModeChange = (m) => {
    if (m === "pdf")  navigate("/pdf/upload");
    if (m === "data") navigate("/data/upload");
  };

  const dataFileProps = {
    activeFileId: activeDataFileId,
    onFileSelect: handleFileSelect,
  };

  return (
    <div className="app-shell">
      <TopNav mode={mode} onModeChange={handleModeChange} />
      <div className="app-body">
        <Sidebar mode={mode} />
        <Routes>
          {/* PDF */}
          <Route path="/pdf/upload"  element={<PdfUpload />} />
          <Route path="/pdf/chat"    element={<PdfChat />} />
          <Route path="/pdf/manage"  element={<PdfManage />} />
          <Route path="/pdf/compare" element={
            <PdfCompare
              compareHistory={compareHistory}
              setCompareHistory={setCompareHistory}
            />
          } />
          <Route path="/pdf/report"  element={<PdfReport />} />
          <Route path="/pdf/eval"    element={<PdfEval />} />

          {/* Data */}
          <Route path="/data/upload"    element={<DataUpload    {...dataFileProps} />} />
          <Route path="/data/chat"      element={<DataChat      {...dataFileProps} />} />
          <Route path="/data/manage"    element={<DataManage    {...dataFileProps} />} />
          <Route path="/data/visualize" element={<DataVisualize {...dataFileProps} />} />
          <Route path="/data/report"    element={<DataReport    {...dataFileProps} />} />
          <Route path="/data/querylog"  element={<DataQueryLog  {...dataFileProps} />} />

          {/* Redirects */}
          <Route path="/"     element={<Navigate to="/pdf/upload" replace />} />
          <Route path="/pdf"  element={<Navigate to="/pdf/upload" replace />} />
          <Route path="/data" element={<Navigate to="/data/upload" replace />} />
          <Route path="*"     element={<Navigate to="/pdf/upload" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public routes */}
            <Route path="/login"    element={<Login />} />
            <Route path="/register" element={<Register />} />

            {/* Protected routes */}
            <Route path="/*" element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            } />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </GoogleOAuthProvider>
  );
}