import { useState, useEffect } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useLocation,
} from "react-router-dom";

import "./styles/global.css";
import TopNav from "./components/shared/TopNav";
import Sidebar from "./components/shared/Sidebar";
import { dataApi } from "./api/client";

// PDF pages
import PdfChat from "./pages/pdf/PdfChat";
import PdfUpload from "./pages/pdf/PdfUpload";
import PdfManage from "./pages/pdf/PdfManage";
import PdfCompare from "./pages/pdf/PdfCompare";
import PdfReport from "./pages/pdf/PdfReport";
import PdfEval from "./pages/pdf/PdfEval";

// Data pages
import DataUpload from "./pages/data/DataUpload";
import DataChat from "./pages/data/DataChat";
import DataManage from "./pages/data/DataManage";
import DataVisualize from "./pages/data/DataVisualize";
import DataReport from "./pages/data/DataReport";
import DataQueryLog from "./pages/data/DataQueryLog";

const STORAGE_KEY = "ragbot_active_file_id";

function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();

  // Active data file — persisted in localStorage
  const [activeDataFileId, setActiveDataFileId] = useState(
    () => localStorage.getItem(STORAGE_KEY) || ""
  );

  // Compare history — persisted in memory across tab switches
  const [compareHistory, setCompareHistory] = useState([]);

  // On mount: validate active file against backend
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
        const stored = localStorage.getItem(STORAGE_KEY);
        const stillExists = stored && all.find((f) => f.file_id === stored);
        if (stillExists) {
          setActiveDataFileId(stored);
        } else {
          const latest = all[all.length - 1];
          setActiveDataFileId(latest.file_id);
          localStorage.setItem(STORAGE_KEY, latest.file_id);
        }
      })
      .catch(() => { });
  }, []);

  const handleFileSelect = (id) => {
    setActiveDataFileId(id);
    if (id) localStorage.setItem(STORAGE_KEY, id);
    else localStorage.removeItem(STORAGE_KEY);
  };

  const mode = location.pathname.startsWith("/data") ? "data" : "pdf";

  const handleModeChange = (m) => {
    if (m === "pdf") navigate("/pdf/upload");
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
          <Route path="/pdf/upload" element={<PdfUpload />} />
          <Route path="/pdf/chat" element={<PdfChat />} />
          <Route path="/pdf/manage" element={<PdfManage />} />
          <Route path="/pdf/compare" element={
            <PdfCompare
              compareHistory={compareHistory}
              setCompareHistory={setCompareHistory}
            />
          } />
          <Route path="/pdf/report" element={<PdfReport />} />
          <Route path="/pdf/eval" element={<PdfEval />} />

          {/* Data */}
          <Route path="/data/upload" element={<DataUpload    {...dataFileProps} />} />
          <Route path="/data/chat" element={<DataChat      {...dataFileProps} />} />
          <Route path="/data/manage" element={<DataManage    {...dataFileProps} />} />
          <Route path="/data/visualize" element={<DataVisualize {...dataFileProps} />} />
          <Route path="/data/report" element={<DataReport    {...dataFileProps} />} />
          <Route path="/data/querylog" element={<DataQueryLog  {...dataFileProps} />} />

          {/* Redirects */}
          <Route path="/" element={<Navigate to="/pdf/upload" replace />} />
          <Route path="/pdf" element={<Navigate to="/pdf/upload" replace />} />
          <Route path="/data" element={<Navigate to="/data/upload" replace />} />
          <Route path="*" element={<Navigate to="/pdf/upload" replace />} />
        </Routes>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}