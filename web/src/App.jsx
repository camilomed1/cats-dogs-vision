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
  const architecture = health?.model?.architecture || "MobileNetV2";

  return (
    <div className="app">
      <header className="header">
        <h1>Cats vs Dogs Classifier</h1>
        <p className="small">
          Model: {architecture}{acc ? ` (${(acc * 100).toFixed(1)}% test accuracy)` : ""}
          {" | "}Server:{" "}
          <span className={online ? "ok" : "error"}>
            {health === null ? "connecting..." : online ? (health.database ? "online" : "online, database offline") : "offline"}
          </span>
        </p>
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
