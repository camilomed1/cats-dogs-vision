import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { captureFrame } from "../images.js";
import Prediction from "./Prediction.jsx";

const LIVE_PAUSE_MS = 250; // pause between live predictions (each one also waits for the server)

export default function WebcamPanel() {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const [stream, setStream] = useState(null);
  const [devices, setDevices] = useState([]);
  const [deviceId, setDeviceId] = useState("");
  const [live, setLive] = useState(false);
  const [result, setResult] = useState(null);
  const [latency, setLatency] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function startCamera(id = deviceId) {
    setError("");
    try {
      stream?.getTracks().forEach((t) => t.stop());
      const s = await navigator.mediaDevices.getUserMedia({
        video: { deviceId: id ? { exact: id } : undefined, width: { ideal: 1280 }, height: { ideal: 720 } },
      });
      setStream(s);
      // Labels are only available after permission is granted.
      const all = await navigator.mediaDevices.enumerateDevices();
      setDevices(all.filter((d) => d.kind === "videoinput"));
      setDeviceId(s.getVideoTracks()[0].getSettings().deviceId || "");
    } catch (e) {
      setError(e.name === "NotAllowedError" ? "Camera permission was denied." : `Could not open camera: ${e.message}`);
    }
  }

  function stopCamera() {
    setLive(false);
    stream?.getTracks().forEach((t) => t.stop());
    setStream(null);
    setResult(null);
  }

  useEffect(() => {
    if (videoRef.current) videoRef.current.srcObject = stream;
  }, [stream]);

  // Release the camera when leaving the tab.
  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);

  // Live loop: capture -> predict (not stored) -> short pause -> repeat, until live is turned off.
  useEffect(() => {
    if (!live || !stream) return;
    let cancelled = false;
    (async () => {
      while (!cancelled) {
        const video = videoRef.current;
        if (video?.videoWidth) {
          const start = performance.now();
          try {
            const { base64 } = captureFrame(video, canvasRef.current, 0.7);
            const r = await api.predict(base64, { source: "webcam", mode: "live" }, false);
            if (!cancelled) {
              setResult(r);
              setLatency(Math.round(performance.now() - start));
              setError("");
            }
          } catch (e) {
            if (!cancelled) setError(e.message);
          }
        }
        await new Promise((r) => setTimeout(r, LIVE_PAUSE_MS));
      }
    })();
    return () => { cancelled = true; };
  }, [live, stream]);

  async function takeSnapshot() {
    const video = videoRef.current;
    if (!video?.videoWidth) return;
    setBusy(true);
    try {
      const { base64, previewUrl } = captureFrame(video, canvasRef.current, 0.92);
      const r = await api.predict(base64, {
        source: "webcam",
        mode: "snapshot",
        filename: `webcam_${new Date().toISOString().replace(/[:.]/g, "-")}.jpg`,
        mimeType: "image/jpeg",
        width: video.videoWidth,
        height: video.videoHeight,
        capturedAt: new Date().toISOString(),
      });
      setResult(r);
      setSnapshots((prev) => [{ previewUrl, result: r }, ...prev].slice(0, 12));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="webcam">
      <div className="webcam-main">
        <div className="video-wrap">
          <video ref={videoRef} autoPlay playsInline muted className={stream ? "" : "hidden"} />
          {!stream && (
            <div className="video-placeholder">
              <div className="dropzone-icon">📷</div>
              <p>Camera is off</p>
            </div>
          )}
          {stream && live && result && (
            <div className="overlay">
              <Prediction result={result} compact />
            </div>
          )}
          {stream && live && <span className="live-badge">● LIVE</span>}
        </div>
        <canvas ref={canvasRef} hidden />

        <div className="controls">
          {!stream ? (
            <button className="primary" onClick={() => startCamera()}>Start camera</button>
          ) : (
            <>
              <button className={live ? "danger" : "primary"} onClick={() => setLive((v) => !v)}>
                {live ? "Stop live prediction" : "Start live prediction"}
              </button>
              <button onClick={takeSnapshot} disabled={busy}>{busy ? "Saving…" : "📸 Snapshot & save"}</button>
              <button onClick={stopCamera}>Turn off camera</button>
              {devices.length > 1 && (
                <select value={deviceId} onChange={(e) => { setDeviceId(e.target.value); startCamera(e.target.value); }}>
                  {devices.map((d, i) => (
                    <option key={d.deviceId} value={d.deviceId}>{d.label || `Camera ${i + 1}`}</option>
                  ))}
                </select>
              )}
            </>
          )}
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      <aside className="webcam-side">
        <h3>Result</h3>
        {result ? (
          <>
            <Prediction result={result} />
            <p className="muted small">
              {live && latency ? `Live · ${latency} ms per prediction · frames are not saved` : result.id ? "Saved to history" : ""}
            </p>
          </>
        ) : (
          <p className="muted">Start live prediction, or take a snapshot to classify and save one frame.</p>
        )}

        {snapshots.length > 0 && (
          <>
            <h3>Saved snapshots</h3>
            <div className="snapshots">
              {snapshots.map((s, i) => (
                <figure key={i}>
                  <img src={s.previewUrl} alt="snapshot" />
                  <figcaption className={s.result.label}>
                    {s.result.label} {(s.result.confidence * 100).toFixed(0)}%
                  </figcaption>
                </figure>
              ))}
            </div>
          </>
        )}
      </aside>
    </section>
  );
}
