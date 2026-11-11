"""IP camera station: a client that watches a camera stream and classifies it live.

- Reads any camera OpenCV can open: a Tapo / IP camera over RTSP, an HTTP (MJPEG) camera,
  a local webcam ("0") or a video file (useful for testing).
- Sends frames to the Flask backend (base64 + metadata, client "ipcamera") without storing them.
- When the same animal is seen with high confidence in several frames in a row, it saves
  one snapshot to MongoDB (a "detection event").
- Serves the labeled video as MJPEG, like the professor's Tapo example, so a browser can show it
  with <img src="http://<pc>:5001/video">.
- Listens on MQTT topic PREFIX/command: {"command": "SNAPSHOT"} (e.g. from the ESP32 button) saves the current frame.

Run:  .venv\\Scripts\\python station.py      (settings in .env, see .env.example)
"""
import base64
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import cv2
import paho.mqtt.client as mqtt
import requests
from dotenv import load_dotenv
from flask import Flask, Response, jsonify
from flask_cors import CORS

load_dotenv(Path(__file__).resolve().parent / ".env")

CAMERA_URL = os.getenv("CAMERA_URL", "0")
CAMERA_NAME = os.getenv("CAMERA_NAME", "IP camera")
API_URL = os.getenv("API_URL", "http://127.0.0.1:5000").rstrip("/")
STATION_PORT = int(os.getenv("STATION_PORT", "5001"))

PREDICT_EVERY_S = float(os.getenv("PREDICT_EVERY_S", "0.3"))    # pause between live predictions
EVENT_FRAMES = int(os.getenv("EVENT_FRAMES", "3"))              # consecutive frames needed for an event
EVENT_CONFIDENCE = float(os.getenv("EVENT_CONFIDENCE", "0.90"))  # minimum confidence for those frames
EVENT_COOLDOWN_S = float(os.getenv("EVENT_COOLDOWN_S", "15"))    # minimum time between events of the same animal

MQTT_ENABLED = os.getenv("MQTT_ENABLED", "true").lower() == "true"
MQTT_HOST = os.getenv("MQTT_HOST", "broker.emqx.io")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_PREFIX = os.getenv("MQTT_PREFIX", "catsdogs-vision/camilomed1").rstrip("/")

IS_FILE = os.path.isfile(CAMERA_URL)
NAMES = {"cat": "Cat", "dog": "Dog", "uncertain": "Uncertain"}


def safe_url(url: str) -> str:
    """Removes the username and password from an RTSP/HTTP URL before showing or storing it."""
    parts = urlsplit(url)
    if parts.username or parts.password:
        netloc = parts.hostname + (f":{parts.port}" if parts.port else "")
        return urlunsplit(parts._replace(netloc=netloc))
    return url


def open_capture(url: str):
    if url.isdigit():  # local webcam index
        cap = cv2.VideoCapture(int(url), cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    else:              # rtsp://, http://, or a video file
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # keep only the newest frame (less delay on RTSP)
    return cap


def resize_max(frame, max_width):
    h, w = frame.shape[:2]
    if w <= max_width:
        return frame
    return cv2.resize(frame, (max_width, round(h * max_width / w)), interpolation=cv2.INTER_AREA)


def encode_jpeg(frame, quality):
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Could not encode frame")
    return buf.tobytes()


def format_result(r):
    return f"{NAMES[r['label']]} ({r['confidence'] * 100:.1f}%)"


def api_predict(image_bytes, metadata, store):
    body = {
        "image": base64.b64encode(image_bytes).decode("ascii"),
        "metadata": {"client": "ipcamera", "source": "stream", **metadata},
        "store": store,
    }
    try:
        r = requests.post(f"{API_URL}/api/predict", json=body, timeout=10)
    except requests.RequestException:
        raise RuntimeError(f"Cannot reach the backend at {API_URL}")
    if not r.ok:
        raise RuntimeError(r.json().get("error", f"Server error ({r.status_code})"))
    return r.json()


def draw_text(frame, text, org, scale, color=(255, 255, 255)):
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 4, cv2.LINE_AA)  # outline
    cv2.putText(frame, text, org, cv2.FONT_HERSHEY_SIMPLEX, scale, color, 1 + int(scale > 0.7), cv2.LINE_AA)


class Station:
    def __init__(self):
        self.lock = threading.Lock()
        self.new_frame = threading.Condition(self.lock)
        self.running = True
        # camera
        self.frame = None          # newest raw frame (BGR)
        self.jpeg = None           # newest labeled frame as JPEG, for the MJPEG stream
        self.frame_id = 0
        self.connected = False
        self.camera_error = ""
        self.fps = 0.0
        # predictions
        self.result = None
        self.latency_ms = None
        self.api_error = ""
        self.streak_label, self.streak = None, 0
        self.last_event_at = {}
        self.saved = 0
        self.last_saved = None
        self.mqtt_connected = False

    # ------------------------------------------------------------ camera
    def read_loop(self):
        while self.running:
            cap = open_capture(CAMERA_URL)
            if not cap.isOpened():
                with self.lock:
                    self.connected = False
                    self.camera_error = f"Could not open camera {safe_url(CAMERA_URL)}. Retrying..."
                print(self.camera_error)
                time.sleep(3)
                continue
            print(f"Camera connected: {safe_url(CAMERA_URL)}")
            file_delay = 1 / (cap.get(cv2.CAP_PROP_FPS) or 25) if IS_FILE else 0
            fails = 0
            while self.running:
                ok, frame = cap.read()
                if not ok:
                    fails += 1
                    if IS_FILE or fails > 50:  # end of video file (loop it) or stream lost (reconnect)
                        break
                    time.sleep(0.05)
                    continue
                fails = 0
                self.publish_frame(frame)
                if file_delay:
                    time.sleep(file_delay)  # play files at their real speed
            cap.release()
            if not IS_FILE:
                with self.lock:
                    self.connected = False
                    self.camera_error = "Stream lost. Reconnecting..."
                print(self.camera_error)
                time.sleep(2)

    def publish_frame(self, frame):
        now = time.time()
        shown = self.annotate(resize_max(frame, 1280))
        jpeg = encode_jpeg(shown, 75)
        with self.new_frame:
            if self.frame is not None and now > self._last_frame_at:
                self.fps = 0.9 * self.fps + 0.1 * (1 / (now - self._last_frame_at))
            self._last_frame_at = now
            self.frame, self.jpeg = frame, jpeg
            self.frame_id += 1
            self.connected, self.camera_error = True, ""
            self.new_frame.notify_all()

    _last_frame_at = 0.0

    def annotate(self, frame):
        frame = frame.copy()
        h = frame.shape[0]
        with self.lock:
            result, api_error, last_saved = self.result, self.api_error, self.last_saved
        draw_text(frame, f"{CAMERA_NAME}  {datetime.now():%H:%M:%S}", (10, 25), 0.6)
        text = api_error or (format_result(result) if result else "Waiting for prediction...")
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2)
        cv2.rectangle(frame, (10, h - th - 30), (30 + tw, h - 10), (255, 255, 255), -1)
        cv2.putText(frame, text, (20, h - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                    (0, 0, 204) if api_error else (0, 0, 0), 2, cv2.LINE_AA)
        if last_saved and time.time() - last_saved["time"] < 2:
            draw_text(frame, "SAVED", (frame.shape[1] - 110, 30), 0.8, (0, 0, 255))
        return frame

    # ------------------------------------------------------------ predictions
    def metadata(self, frame, mode, **extra):
        h, w = frame.shape[:2]
        slug = re.sub(r"[^a-z0-9]+", "_", CAMERA_NAME.lower()).strip("_") or "camera"
        return {
            "mode": mode,
            "cameraName": CAMERA_NAME,
            "cameraUrl": safe_url(CAMERA_URL),
            "filename": f"{slug}_{datetime.now():%Y%m%d_%H%M%S}.jpg",
            "mimeType": "image/jpeg",
            "width": w,
            "height": h,
            "capturedAt": datetime.now(timezone.utc).isoformat(),
            **extra,
        }

    def predict_loop(self):
        last_id = -1
        while self.running:
            with self.lock:
                frame, frame_id = self.frame, self.frame_id
            if frame is None or frame_id == last_id:
                time.sleep(0.05)
                continue
            last_id = frame_id
            small = resize_max(frame, 640)  # the model only needs 180x180; smaller upload = faster
            start = time.perf_counter()
            try:
                result = api_predict(encode_jpeg(small, 80), self.metadata(small, "live"), store=False)
            except Exception as e:
                with self.lock:
                    self.api_error = str(e)
                time.sleep(1)
                continue
            with self.lock:
                self.result = result
                self.latency_ms = round((time.perf_counter() - start) * 1000)
                self.api_error = ""
            self.check_event(frame, result)
            time.sleep(PREDICT_EVERY_S)

    def check_event(self, frame, result):
        """Saves one snapshot when the same animal is seen confidently in EVENT_FRAMES frames in a row."""
        label = result["label"]
        if label in ("cat", "dog") and result["confidence"] >= EVENT_CONFIDENCE:
            self.streak = self.streak + 1 if label == self.streak_label else 1
            self.streak_label = label
        else:
            self.streak_label, self.streak = None, 0
            return
        # == (not >=): one event per appearance, not one every frame while the animal stays in view
        if self.streak == EVENT_FRAMES and time.time() - self.last_event_at.get(label, 0) >= EVENT_COOLDOWN_S:
            self.last_event_at[label] = time.time()
            try:
                self.save(frame, "event", eventFrames=EVENT_FRAMES, eventConfidence=EVENT_CONFIDENCE)
            except Exception as e:
                print("Could not save event:", e)

    def save(self, frame, mode, **extra):
        big = resize_max(frame, 1920)
        result = api_predict(encode_jpeg(big, 90), self.metadata(big, mode, **extra), store=True)
        with self.lock:
            self.saved += 1
            self.last_saved = {"time": time.time(), "mode": mode, "id": result.get("id"),
                               "label": result["label"], "confidence": result["confidence"],
                               "at": datetime.now(timezone.utc).isoformat()}
        print(f"Saved {mode}: {format_result(result)} (id {result.get('id')})")
        return result

    def status(self):
        with self.lock:
            h, w = self.frame.shape[:2] if self.frame is not None else (None, None)
            return {
                "camera": {"name": CAMERA_NAME, "source": safe_url(CAMERA_URL), "connected": self.connected,
                           "error": self.camera_error, "width": w, "height": h, "fps": round(self.fps, 1)},
                "prediction": self.result,
                "latencyMs": self.latency_ms,
                "apiError": self.api_error,
                "streak": {"label": self.streak_label, "count": self.streak, "needed": EVENT_FRAMES},
                "settings": {"eventFrames": EVENT_FRAMES, "eventConfidence": EVENT_CONFIDENCE,
                             "eventCooldownS": EVENT_COOLDOWN_S, "predictEveryS": PREDICT_EVERY_S},
                "mqtt": {"enabled": MQTT_ENABLED, "connected": self.mqtt_connected,
                         "commandTopic": f"{MQTT_PREFIX}/command" if MQTT_ENABLED else None},
                "saved": self.saved,
                "lastSaved": {k: v for k, v in self.last_saved.items() if k != "time"} if self.last_saved else None,
            }

    def mjpeg(self):
        last_id = -1
        while self.running:
            with self.new_frame:
                self.new_frame.wait_for(lambda: self.frame_id != last_id, timeout=5)
                jpeg, last_id = self.jpeg, self.frame_id
            if jpeg is None:
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"


def start_mqtt(station: Station):
    """Subscribes to PREFIX/command. {"command": "SNAPSHOT", "device": "..."} saves the current frame."""
    if not MQTT_ENABLED:
        return None
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"catsdogs-station-{uuid.uuid4().hex[:8]}")
    status_topic = f"{MQTT_PREFIX}/station/status"
    client.will_set(status_topic, json.dumps({"camera": CAMERA_NAME, "status": "offline"}), retain=True)

    def on_connect(c, userdata, flags, reason_code, properties):
        station.mqtt_connected = not reason_code.is_failure
        if station.mqtt_connected:
            c.subscribe(f"{MQTT_PREFIX}/command")
            c.publish(status_topic, json.dumps({"camera": CAMERA_NAME, "status": "online"}), retain=True)
            print(f"MQTT connected to {MQTT_HOST}:{MQTT_PORT}, listening on {MQTT_PREFIX}/command")

    def on_disconnect(c, userdata, flags, reason_code, properties):
        station.mqtt_connected = False

    def on_message(c, userdata, msg):
        try:
            command = json.loads(msg.payload)
        except ValueError:
            print("Ignoring non-JSON command:", msg.payload[:100])
            return
        if not isinstance(command, dict) or command.get("command") != "SNAPSHOT":
            return
        with station.lock:
            frame = station.frame
        if frame is None:
            return
        device = str(command.get("device", "unknown"))[:40]
        print(f"SNAPSHOT requested by {device}")
        # Saving calls the backend over HTTP; do it in another thread so MQTT is never blocked.
        threading.Thread(target=station.save, args=(frame, "remote"), kwargs={"requestedBy": device}, daemon=True).start()

    client.on_connect, client.on_disconnect, client.on_message = on_connect, on_disconnect, on_message
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    return client


def create_app(station: Station) -> Flask:
    app = Flask(__name__)
    CORS(app)

    @app.get("/")
    def index():
        return f"""<html><body style="font-family: Arial">
        <h2>{CAMERA_NAME}</h2><img src="/video" width="800">
        <p><a href="/status">status</a></p></body></html>"""

    @app.get("/video")
    def video():
        return Response(station.mjpeg(), mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.get("/status")
    def status():
        return jsonify(station.status())

    @app.post("/snapshot")
    def snapshot():
        with station.lock:
            frame = station.frame
        if frame is None:
            return jsonify(error="The camera has no frame yet"), 503
        try:
            return jsonify(station.save(frame, "manual"))
        except Exception as e:
            return jsonify(error=str(e)), 502

    return app


if __name__ == "__main__":
    station = Station()
    threading.Thread(target=station.read_loop, daemon=True).start()
    threading.Thread(target=station.predict_loop, daemon=True).start()
    start_mqtt(station)
    print(f"Camera: {safe_url(CAMERA_URL)} | Backend: {API_URL} | Stream: http://0.0.0.0:{STATION_PORT}/video")
    create_app(station).run(host="0.0.0.0", port=STATION_PORT, threaded=True)
