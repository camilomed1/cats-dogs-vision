"""Quick camera check for the lab: is the camera reachable, and does the video open?

Run:  .venv\\Scripts\\python check_camera.py                 (uses CAMERA_URL from .env)
      .venv\\Scripts\\python check_camera.py "rtsp://user:pass@192.168.210.6:554/stream1"
"""
import os
import socket
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

import cv2  # noqa: E402  (after setting the FFmpeg options)

from station import safe_url  # noqa: E402


def my_ips():
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
    except OSError:
        return []


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CAMERA_URL", "0")
    print(f"Camera URL : {safe_url(url)}")
    print(f"This PC    : {', '.join(my_ips()) or 'unknown'}")

    parts = urlsplit(url)
    if parts.scheme in ("rtsp", "http", "https") and parts.hostname:
        host, port = parts.hostname, parts.port or {"rtsp": 554, "http": 80, "https": 443}[parts.scheme]
        print(f"\n1) Network: connecting to {host}:{port} ...")
        try:
            with socket.create_connection((host, port), timeout=4):
                print("   OK, the camera answers on the network.")
        except OSError as e:
            print(f"   FAILED ({e}).")
            print("   -> The PC cannot reach the camera. Check that:")
            print("      - this PC is on the same Wi-Fi/network as the camera (compare the first numbers of the IPs above),")
            print("      - the camera IP is correct (see it in the Tapo app: camera > settings > device info),")
            print("      - the camera is on.")
            return 1

    print("\n2) Video: opening the stream ...")
    start = time.time()
    if url.isdigit():
        cap = cv2.VideoCapture(int(url), cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    else:
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG, [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 8000,
                                                   cv2.CAP_PROP_READ_TIMEOUT_MSEC, 8000])
    if not cap.isOpened():
        print(f"   FAILED after {time.time() - start:.1f} s.")
        if url.startswith("rtsp"):
            print("   -> The camera answers but the video does not open. Usually:")
            print("      - wrong camera account username/password (Tapo app > Advanced settings > Camera account),")
            print("      - wrong path: use /stream1 (HD) or /stream2 (lower quality).")
        return 1

    frames, first = 0, None
    t0 = time.time()
    while frames < 30 and time.time() - t0 < 10:
        ok, frame = cap.read()
        if ok:
            frames += 1
            first = frame if first is None else first
    cap.release()
    if not frames:
        print("   FAILED: the stream opened but sent no frames.")
        return 1

    h, w = first.shape[:2]
    out = Path(__file__).resolve().parent / "check_camera.jpg"
    cv2.imwrite(str(out), first)
    speed = "video file" if os.path.isfile(url) else f"about {frames / (time.time() - t0):.1f} fps"
    print(f"   OK: {w}x{h}, {speed}. First frame saved to {out.name}")
    print("\nThe camera works. Start the station with:  .venv\\Scripts\\python station.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
