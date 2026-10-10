import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";
import Prediction from "./Prediction.jsx";

const CLIENTS = ["", "web", "desktop", "mobile"];
const LABELS = ["", "cat", "dog", "uncertain"];

export default function HistoryPanel() {
  const [items, setItems] = useState([]);
  const [client, setClient] = useState("");
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await api.history(100, client));
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [client]);

  useEffect(() => { load(); }, [load]);

  async function remove(item) {
    if (!confirm(`Delete this prediction and its image from MongoDB?`)) return;
    try {
      await api.deletePrediction(item.id);
      setItems((prev) => prev.filter((i) => i.id !== item.id));
      setSelected(null);
    } catch (e) {
      setError(e.message);
    }
  }

  const shown = label ? items.filter((i) => i.label === label) : items;
  const count = (l) => items.filter((i) => i.label === l).length;

  return (
    <section>
      <div className="toolbar">
        <div className="filters">
          <select value={client} onChange={(e) => setClient(e.target.value)}>
            {CLIENTS.map((c) => <option key={c} value={c}>{c ? `Client: ${c}` : "All clients"}</option>)}
          </select>
          <select value={label} onChange={(e) => setLabel(e.target.value)}>
            {LABELS.map((l) => <option key={l} value={l}>{l ? `Label: ${l}` : "All labels"}</option>)}
          </select>
          <button onClick={load} disabled={loading}>{loading ? "Loading..." : "Refresh"}</button>
        </div>
        <span className="small">
          Cats: {count("cat")} | Dogs: {count("dog")} | Uncertain: {count("uncertain")}
        </span>
      </div>

      {error && <p className="error">{error}</p>}
      {!loading && !error && shown.length === 0 && (
        <p className="empty">No predictions yet. Classify some images in the Upload or Webcam tab.</p>
      )}

      <div className="grid">
        {shown.map((it) => (
          <article key={it.id} className="card clickable" onClick={() => setSelected(it)}>
            <div className="thumb">
              <img src={api.imageUrl(it.imageUrl)} alt={it.label} loading="lazy" />
            </div>
            <div className="card-body">
              <Prediction result={it} compact />
              <p className="muted small">
                {it.metadata.client} / {it.metadata.source || "?"}
                <br />
                {new Date(it.createdAt).toLocaleString()}
              </p>
            </div>
          </article>
        ))}
      </div>

      {selected && (
        <div className="modal-backdrop" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <img src={api.imageUrl(selected.imageUrl)} alt={selected.label} />
            <div className="modal-body">
              <Prediction result={selected} />
              <h4>Metadata (sent by the client)</h4>
              <pre>{JSON.stringify(selected.metadata, null, 2)}</pre>
              <h4>Stored image (GridFS)</h4>
              <pre>{JSON.stringify({ imageId: selected.imageId, ...selected.image }, null, 2)}</pre>
              <div className="controls">
                <button onClick={() => remove(selected)}>Delete</button>
                <button onClick={() => setSelected(null)}>Close</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
