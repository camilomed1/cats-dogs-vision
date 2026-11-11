import { useEffect, useState } from "react";
import { api } from "../api.js";
import Prediction from "./Prediction.jsx";

// The camera station (camera_station/station.py) runs on the same PC as the backend, on port 5001.
const STATION = import.meta.env.VITE_STATION_URL || `${location.protocol}//${location.hostname}:5001`;

export default function IpCameraPanel() {
  const [status, setStatus] = useState(null);
  const [offline, setOffline] = useState(false);
  const [streamKey, setStreamKey] = useState(0); // changing it reconnects the video
  const [events, setEvents] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const poll = () =>
      fetch(`${STATION}/status`)
        .then((r) => r.json())
        .then((s) => {
          if (!active) return;
          setStatus(s);
          setOffline((wasOffline) => {
            if (wasOffline) setStreamKey((k) => k + 1); // station came back: reconnect the video
            return false;
          });
        })
        .catch(() => active && setOffline(true));
    poll();
    const id = setInterval(poll, 1000);
    return () => { active = false; clearInterval(id); };
  }, []);

  // Reload the saved detections whenever the station saves a new one.
  const savedCount = status?.saved;
  useEffect(() => {
    api.history(8, "ipcamera").then(setEvents).catch(() => {});
  }, [savedCount]);

  async function snapshot() {
    setBusy(true);
    setError("");
    try {
      const res = await fetch(`${STATION}/snapshot`, { method: "POST" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || "Snapshot failed");
    } catch (e) {
      setError(e.message === "Failed to fetch" ? "The camera station is not running." : e.message);
    } finally {
      setBusy(false);
    }
  }

  const cam = status?.camera;
  const settings = status?.settings;

  return (
    <section className="webcam">
      <div className="webcam-main">
        <div className="video-wrap">
          {offline ? (
            <div className="video-placeholder">
              <div>
                <p>The camera station is not running.</p>
                <p className="small">
                  Start it with: cd camera_station, then .venv\Scripts\python station.py
                </p>
              </div>
            </div>
          ) : (
            <img key={streamKey} src={`${STATION}/video`} alt="IP camera" className="stream" />
          )}
        </div>
        <div className="controls">
          <button onClick={snapshot} disabled={busy || offline || !cam?.connected}>
            {busy ? "Saving..." : "Snapshot and save"}
          </button>
          <button onClick={() => setStreamKey((k) => k + 1)}>Reconnect video</button>
        </div>
        {error && <p className="error">{error}</p>}
        {cam && (
          <p className="small">
            Camera: {cam.name} ({cam.source}) |{" "}
            <span className={cam.connected ? "ok" : "error"}>{cam.connected ? "connected" : cam.error || "disconnected"}</span>
            {cam.connected && ` | ${cam.width}x${cam.height}, ${cam.fps} fps`}
          </p>
        )}
      </div>

      <aside className="webcam-side">
        <h3>Live result</h3>
        {status?.apiError ? (
          <p className="error">{status.apiError}</p>
        ) : status?.prediction ? (
          <>
            <Prediction result={status.prediction} />
            <p className="muted small">{status.latencyMs} ms per prediction. Live frames are not saved.</p>
          </>
        ) : (
          <p className="muted">{offline ? "-" : "Waiting for the first prediction..."}</p>
        )}

        {settings && (
          <p className="muted small">
            A snapshot is saved automatically when the same animal is seen with at least{" "}
            {(settings.eventConfidence * 100).toFixed(0)}% confidence in {settings.eventFrames} predictions in a row
            {status.streak.label && ` (now: ${status.streak.label} ${status.streak.count}/${status.streak.needed})`}.
          </p>
        )}

        <h3>Saved detections</h3>
        {events.length === 0 && <p className="muted small">None yet.</p>}
        <div className="snapshots">
          {events.map((e) => (
            <figure key={e.id} title={`${e.metadata.mode} - ${new Date(e.createdAt).toLocaleString()}`}>
              <img src={api.imageUrl(e.imageUrl)} alt={e.label} />
              <figcaption>
                {e.label} {(e.confidence * 100).toFixed(0)}%
              </figcaption>
            </figure>
          ))}
        </div>
      </aside>
    </section>
  );
}
