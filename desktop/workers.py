"""Background work so the window never freezes while waiting for the server or the camera."""
import threading
import time

import cv2
from PySide6.QtCore import QObject, QRunnable, QThread, QThreadPool, Signal
from PySide6.QtGui import QImage


class _TaskSignals(QObject):
    done = Signal(object, object)   # tag, result
    failed = Signal(object, str)    # tag, error message
    finished = Signal(object)       # the task itself, always emitted last


class _Task(QRunnable):
    def __init__(self, fn, tag):
        super().__init__()
        self.setAutoDelete(False)
        self.fn, self.tag = fn, tag
        self.signals = _TaskSignals()

    def run(self):
        try:
            result = self.fn()
        except Exception as e:
            self.signals.failed.emit(self.tag, str(e))
        else:
            self.signals.done.emit(self.tag, result)
        self.signals.finished.emit(self)


class _Keeper(QObject):
    """Lives in the GUI thread and holds running tasks until their callbacks have been delivered."""

    def __init__(self):
        super().__init__()
        self.tasks = set()

    def release(self, task):
        self.tasks.discard(task)


_keeper = None


def run_async(fn, on_done=None, on_error=None, tag=None):
    """Runs fn() in the thread pool. Callbacks run in the GUI thread as on_done(tag, result) / on_error(tag, msg).
    Pass bound methods of widgets as callbacks so Qt delivers them in the GUI thread."""
    global _keeper
    if _keeper is None:
        _keeper = _Keeper()
    task = _Task(fn, tag)
    if on_done:
        task.signals.done.connect(on_done)
    if on_error:
        task.signals.failed.connect(on_error)
    task.signals.finished.connect(_keeper.release)
    _keeper.tasks.add(task)
    QThreadPool.globalInstance().start(task)


def frame_to_qimage(frame) -> QImage:
    """OpenCV BGR frame -> QImage (copied, so it is safe to send to another thread)."""
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888).copy()


def encode_jpeg(frame, quality: int) -> bytes:
    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Could not encode the camera frame")
    return buf.tobytes()


class CameraThread(QThread):
    """Reads frames from a webcam and emits them as QImages. The latest raw frame is kept for predictions."""
    frame_ready = Signal(QImage)
    failed = Signal(str)

    def __init__(self, index: int):
        super().__init__()
        self.index = index
        self.overlay_text = ""  # drawn on the video while live prediction is on
        self._running = True
        self._lock = threading.Lock()
        self._latest = None

    def latest_frame(self):
        with self._lock:
            return None if self._latest is None else self._latest.copy()

    def stop(self):
        self._running = False
        self.wait(2000)

    def run(self):
        cap = cv2.VideoCapture(self.index, cv2.CAP_DSHOW)  # DirectShow opens much faster on Windows
        if not cap.isOpened():
            self.failed.emit(f"Could not open camera {self.index}.")
            return
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                with self._lock:
                    self._latest = frame
                shown = frame.copy()
                if self.overlay_text:
                    draw_label(shown, self.overlay_text)
                self.frame_ready.emit(frame_to_qimage(shown))
        finally:
            cap.release()


def draw_label(frame, text):
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2
    (tw, th), _ = cv2.getTextSize(text, font, scale, thickness)
    h = frame.shape[0]
    cv2.rectangle(frame, (10, h - th - 30), (30 + tw, h - 10), (255, 255, 255), -1)
    cv2.putText(frame, text, (20, h - 20), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)


class LivePredictor(QThread):
    """Sends the latest camera frame to the API in a loop (frames are not stored)."""
    result = Signal(dict, int)  # prediction, latency in ms
    failed = Signal(str)

    PAUSE_S = 0.25

    def __init__(self, api, camera: CameraThread):
        super().__init__()
        self.api, self.camera = api, camera
        self._running = True

    def stop(self):
        self._running = False
        self.wait(5000)

    def run(self):
        while self._running:
            frame = self.camera.latest_frame()
            if frame is not None:
                start = time.perf_counter()
                try:
                    r = self.api.predict(encode_jpeg(frame, 70), {"source": "webcam", "mode": "live"}, store=False)
                    self.result.emit(r, int((time.perf_counter() - start) * 1000))
                except Exception as e:
                    self.failed.emit(str(e))
                    time.sleep(1)
            time.sleep(self.PAUSE_S)
