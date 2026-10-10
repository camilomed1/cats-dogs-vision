import { useEffect, useState } from "react";
import { api } from "./api.js";
import UploadPanel from "./components/UploadPanel.jsx";
import WebcamPanel from "./components/WebcamPanel.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";

const TABS = [
  { id: "upload", label: "Upload" },
  { id: "webcam", label: "Webcam" },
  { id: "history", label: "History" },
];

export default function App() {
  const [tab, setTab] = useState("upload");
  const [health, setHealth] = useState(null);

  useEffect(() => {
    const check = () => api.health().then(setHealth).catch(() => setHealth({ status: "down" }));
    check();
    const id = setInterval(check, 10000);
    return () => clearInterval(id);
  }, []);

  const online = health?.status === "ok";
  const acc = health?.model?.test_accuracy;

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>🐾 Cats vs Dogs</h1>
          <p className="subtitle">
            MobileNetV2 transfer learning{acc ? ` · ${(acc * 100).toFixed(1)}% test accuracy` : ""}
          </p>
        </div>
        <div className={`status ${online ? "ok" : "down"}`} title="Backend status">
          <span className="dot" />
          {health === null ? "Connecting…" : online ? (health.database ? "Server online" : "Server online · DB offline") : "Server offline"}
        </div>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      <main>
        {tab === "upload" && <UploadPanel />}
        {tab === "webcam" && <WebcamPanel />}
        {tab === "history" && <HistoryPanel />}
      </main>
    </div>
  );
}
