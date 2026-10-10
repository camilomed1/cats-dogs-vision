import { useRef, useState } from "react";
import { api } from "../api.js";
import { readFile } from "../images.js";
import Prediction from "./Prediction.jsx";

const ACCEPT = "image/jpeg,image/png,image/bmp,image/gif,image/webp";
let nextKey = 0;

export default function UploadPanel() {
  const [items, setItems] = useState([]);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const update = (key, patch) =>
    setItems((prev) => prev.map((it) => (it.key === key ? { ...it, ...patch } : it)));

  async function handleFiles(fileList) {
    const files = [...fileList].filter((f) => f.type.startsWith("image/"));
    // Process one at a time so the server isn't flooded when many files are dropped.
    for (const file of files) {
      const key = nextKey++;
      setItems((prev) => [{ key, name: file.name, status: "loading" }, ...prev]);
      try {
        const { base64, previewUrl, width, height } = await readFile(file);
        update(key, { previewUrl });
        const result = await api.predict(base64, {
          source: "file",
          filename: file.name,
          mimeType: file.type,
          sizeBytes: file.size,
          width,
          height,
          lastModified: new Date(file.lastModified).toISOString(),
          capturedAt: new Date().toISOString(),
        });
        update(key, { status: "done", result });
      } catch (e) {
        update(key, { status: "error", error: e.message });
      }
    }
  }

  return (
    <section>
      <div
        className={`dropzone ${dragging ? "dragging" : ""}`}
        onClick={() => inputRef.current.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
      >
        <p>Drop images here or click to choose files</p>
        <p className="muted small">JPEG, PNG, BMP, GIF or WEBP. You can select several at once.</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          multiple
          hidden
          onChange={(e) => { handleFiles(e.target.files); e.target.value = ""; }}
        />
      </div>

      {items.length > 0 && (
        <div className="toolbar">
          <span className="muted">{items.length} image{items.length > 1 ? "s" : ""} classified this session</span>
          <button className="link" onClick={() => setItems([])}>Clear</button>
        </div>
      )}

      <div className="grid">
        {items.map((it) => (
          <article key={it.key} className="card">
            <div className="thumb">
              {it.previewUrl && <img src={it.previewUrl} alt={it.name} />}
            </div>
            <div className="card-body">
              <p className="filename" title={it.name}>{it.name}</p>
              {it.status === "loading" && <p className="muted">Classifying...</p>}
              {it.status === "error" && <p className="error">{it.error}</p>}
              {it.status === "done" && <Prediction result={it.result} />}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
