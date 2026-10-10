"""The three tabs of the desktop app: Upload, Webcam and History."""
import json
import mimetypes
import os
from datetime import datetime, timezone
from itertools import count
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QListView, QListWidget, QListWidgetItem,
    QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from workers import CameraThread, LivePredictor, encode_jpeg, frame_to_qimage, run_async

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"}
NAMES = {"cat": "Cat", "dog": "Dog", "uncertain": "Uncertain"}
THUMB = QSize(180, 135)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def format_result(r):
    return f"{NAMES[r['label']]} ({r['confidence'] * 100:.1f}%)"


def make_thumb(image: QImage) -> QImage:
    return image.scaled(THUMB, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def make_image_list(icon_size=THUMB, grid=QSize(200, 200)) -> QListWidget:
    lst = QListWidget()
    lst.setViewMode(QListView.IconMode)
    lst.setIconSize(icon_size)
    lst.setGridSize(grid)
    lst.setResizeMode(QListView.Adjust)
    lst.setMovement(QListView.Static)
    lst.setWordWrap(True)
    lst.setSpacing(4)
    return lst


class PredictionView(QWidget):
    """Label + confidence bar, like the web client."""

    def __init__(self):
        super().__init__()
        self.label = QLabel()
        self.label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.hint = QLabel()
        self.hint.setWordWrap(True)
        self.hint.setObjectName("muted")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        for w in (self.label, self.bar, self.hint):
            layout.addWidget(w)
        self.clear()

    def clear(self):
        self.label.setText("-")
        self.bar.setValue(0)
        self.hint.hide()

    def set_result(self, r):
        self.label.setText(format_result(r))
        self.bar.setValue(round(r["confidence"] * 100))
        if r["label"] == "uncertain":
            self.hint.setText(f"Best guess: {r['predictedClass']}, but confidence is below "
                              f"{r['threshold'] * 100:.0f}%. It may not be a cat or a dog.")
            self.hint.show()
        else:
            self.hint.hide()


# ---------------------------------------------------------------- Upload

class UploadTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.items = {}
        self.keys = count()
        self.setAcceptDrops(True)

        choose = QPushButton("Choose images...")
        choose.clicked.connect(self.choose_files)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        hint = QLabel("or drag and drop image files into this window. JPEG, PNG, BMP, GIF or WEBP.")
        hint.setObjectName("muted")

        top = QHBoxLayout()
        top.addWidget(choose)
        top.addWidget(hint)
        top.addStretch()
        top.addWidget(clear)

        self.list = make_image_list()
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.list)

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Choose images", "", "Images (*.jpg *.jpeg *.png *.bmp *.gif *.webp)")
        self.add_files(paths)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([u.toLocalFile() for u in event.mimeData().urls()])

    def add_files(self, paths):
        for path in paths:
            if Path(path).suffix.lower() not in IMAGE_EXTS:
                continue
            key = next(self.keys)
            item = QListWidgetItem(f"{Path(path).name}\nClassifying...")
            self.list.insertItem(0, item)
            self.items[key] = item
            run_async(lambda p=path: self.classify_file(p), self.on_done, self.on_error, tag=key)

    def classify_file(self, path):
        """Runs in a worker thread: read the file, build the metadata and call the API."""
        data = Path(path).read_bytes()
        image = QImage.fromData(data)
        if image.isNull():
            raise ValueError("Could not open this image")
        result = self.api.predict(data, {
            "source": "file",
            "filename": Path(path).name,
            "mimeType": mimetypes.guess_type(path)[0] or "application/octet-stream",
            "sizeBytes": len(data),
            "width": image.width(),
            "height": image.height(),
            "lastModified": datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).isoformat(),
            "capturedAt": now_iso(),
        })
        return Path(path).name, make_thumb(image), result

    def on_done(self, key, value):
        item = self.items.pop(key, None)
        if item is None:  # list was cleared meanwhile
            return
        name, thumb, result = value
        item.setIcon(QIcon(QPixmap.fromImage(thumb)))
        item.setText(f"{name}\n{format_result(result)}")

    def on_error(self, key, message):
        item = self.items.pop(key, None)
        if item is not None:
            item.setText(f"{item.text().splitlines()[0]}\nError: {message}")

    def clear(self):
        self.list.clear()
        self.items.clear()


# ---------------------------------------------------------------- Webcam

class WebcamTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.camera = None
        self.live = None

        self.video = QLabel("Camera is off")
        self.video.setObjectName("video")
        self.video.setAlignment(Qt.AlignCenter)
        self.video.setMinimumSize(640, 360)
        # Ignored size policy: otherwise the label grows to fit each frame and the window keeps expanding.
        self.video.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)

        self.camera_select = QComboBox()
        self.camera_select.addItems([f"Camera {i}" for i in range(4)])
        self.camera_button = QPushButton("Start camera")
        self.camera_button.clicked.connect(self.toggle_camera)
        self.live_button = QPushButton("Start live prediction")
        self.live_button.clicked.connect(self.toggle_live)
        self.snapshot_button = QPushButton("Snapshot and save")
        self.snapshot_button.clicked.connect(self.snapshot)

        controls = QHBoxLayout()
        for w in (self.camera_select, self.camera_button, self.live_button, self.snapshot_button):
            controls.addWidget(w)
        controls.addStretch()

        self.error = QLabel()
        self.error.setObjectName("error")

        left = QVBoxLayout()
        left.addWidget(self.video, 1)
        left.addLayout(controls)
        left.addWidget(self.error)

        self.prediction = PredictionView()
        self.info = QLabel("Start live prediction, or take a snapshot to classify and save one frame.")
        self.info.setWordWrap(True)
        self.info.setObjectName("muted")
        self.snapshots = make_image_list(QSize(80, 60), QSize(88, 84))

        side_widget = QWidget()
        side_widget.setObjectName("panel")
        side_widget.setFixedWidth(290)
        side = QVBoxLayout(side_widget)
        side.addWidget(QLabel("<b>Result</b>"))
        side.addWidget(self.prediction)
        side.addWidget(self.info)
        side.addSpacing(10)
        side.addWidget(QLabel("<b>Saved snapshots</b>"))
        side.addWidget(self.snapshots, 1)

        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addWidget(side_widget)
        self.update_buttons()

    def update_buttons(self):
        on = self.camera is not None
        self.camera_button.setText("Turn off camera" if on else "Start camera")
        self.camera_select.setEnabled(not on)
        self.live_button.setEnabled(on)
        self.snapshot_button.setEnabled(on)
        self.live_button.setText("Stop live prediction" if self.live else "Start live prediction")

    def toggle_camera(self):
        if self.camera:
            self.shutdown()
            return
        self.error.clear()
        self.camera = CameraThread(self.camera_select.currentIndex())
        self.camera.frame_ready.connect(self.show_frame)
        self.camera.failed.connect(self.on_camera_failed)
        self.camera.start()
        self.update_buttons()

    def on_camera_failed(self, message):
        self.error.setText(message)
        self.shutdown()

    def show_frame(self, image: QImage):
        pixmap = QPixmap.fromImage(image).scaled(self.video.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.video.setPixmap(pixmap)

    def toggle_live(self):
        if self.live:
            self.stop_live()
        else:
            self.live = LivePredictor(self.api, self.camera)
            self.live.result.connect(self.on_live_result)
            self.live.failed.connect(self.on_live_failed)
            self.live.start()
        self.update_buttons()

    def stop_live(self):
        if self.live:
            self.live.stop()
            self.live = None
        if self.camera:
            self.camera.overlay_text = ""

    def on_live_result(self, result, latency_ms):
        if not self.live:
            return
        self.prediction.set_result(result)
        self.camera.overlay_text = format_result(result)
        self.info.setText(f"Live: {latency_ms} ms per prediction. Frames are not saved.")
        self.error.clear()

    def on_live_failed(self, message):
        self.error.setText(message)

    def snapshot(self):
        frame = self.camera.latest_frame() if self.camera else None
        if frame is None:
            return
        self.snapshot_button.setEnabled(False)
        self.snapshot_button.setText("Saving...")
        index = self.camera.index

        def work():
            h, w = frame.shape[:2]
            result = self.api.predict(encode_jpeg(frame, 92), {
                "source": "webcam",
                "mode": "snapshot",
                "filename": f"webcam_{datetime.now():%Y%m%d_%H%M%S}.jpg",
                "mimeType": "image/jpeg",
                "width": w,
                "height": h,
                "cameraIndex": index,
                "capturedAt": now_iso(),
            })
            return make_thumb(frame_to_qimage(frame)), result

        run_async(work, self.on_snapshot_done, self.on_snapshot_failed)

    def on_snapshot_done(self, _, value):
        thumb, result = value
        self.prediction.set_result(result)
        self.info.setText("Saved to history.")
        item = QListWidgetItem(QIcon(QPixmap.fromImage(thumb)), format_result(result))
        self.snapshots.insertItem(0, item)
        self.snapshot_button.setText("Snapshot and save")
        self.update_buttons()

    def on_snapshot_failed(self, _, message):
        self.error.setText(message)
        self.snapshot_button.setText("Snapshot and save")
        self.update_buttons()

    def shutdown(self):
        self.stop_live()
        if self.camera:
            self.camera.stop()
            self.camera = None
        self.video.clear()
        self.video.setText("Camera is off")
        self.update_buttons()


# ---------------------------------------------------------------- History

class HistoryTab(QWidget):
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.records = []
        self.thumbs = {}      # prediction id -> QPixmap
        self.request_id = 0   # ignore answers from older refreshes

        self.client_filter = QComboBox()
        self.client_filter.addItem("All clients", "")
        for c in ("web", "desktop", "mobile"):
            self.client_filter.addItem(f"Client: {c}", c)
        self.client_filter.currentIndexChanged.connect(self.refresh)

        self.label_filter = QComboBox()
        self.label_filter.addItem("All labels", "")
        for l in ("cat", "dog", "uncertain"):
            self.label_filter.addItem(f"Label: {l}", l)
        self.label_filter.currentIndexChanged.connect(self.render)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        self.counts = QLabel()

        top = QHBoxLayout()
        for w in (self.client_filter, self.label_filter, self.refresh_button):
            top.addWidget(w)
        top.addStretch()
        top.addWidget(self.counts)

        self.status = QLabel()
        self.status.setObjectName("muted")
        self.list = make_image_list(grid=QSize(200, 220))
        self.list.itemDoubleClicked.connect(self.open_details)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(QLabel("Double-click an image to see its details."))
        layout.addWidget(self.status)
        layout.addWidget(self.list)

    def refresh(self):
        self.request_id += 1
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Loading...")
        client = self.client_filter.currentData()
        run_async(lambda: self.api.history(100, client), self.on_history, self.on_history_error, tag=self.request_id)

    def on_history(self, request_id, records):
        if request_id != self.request_id:
            return
        self.records = records
        self.reset_refresh_button()
        self.status.clear()
        self.render()

    def on_history_error(self, request_id, message):
        if request_id == self.request_id:
            self.reset_refresh_button()
            self.status.setText(message)

    def reset_refresh_button(self):
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh")

    def render(self):
        label = self.label_filter.currentData()
        n = {l: sum(r["label"] == l for r in self.records) for l in NAMES}
        self.counts.setText(f"Cats: {n['cat']} | Dogs: {n['dog']} | Uncertain: {n['uncertain']}")

        self.list.clear()
        shown = [r for r in self.records if not label or r["label"] == label]
        if not shown:
            self.status.setText("No predictions yet.")
        for r in shown:
            created = datetime.fromisoformat(r["createdAt"]).astimezone()
            meta = r["metadata"]
            item = QListWidgetItem(
                f"{format_result(r)}\n{meta.get('client')} / {meta.get('source', '?')}\n{created:%Y-%m-%d %H:%M}")
            item.setData(Qt.UserRole, r)
            if r["id"] in self.thumbs:
                item.setIcon(QIcon(self.thumbs[r["id"]]))
            else:
                url = r["imageUrl"]
                run_async(lambda u=url: make_thumb(QImage.fromData(self.api.image(u))), self.on_thumb, tag=r["id"])
            self.list.addItem(item)

    def on_thumb(self, prediction_id, image):
        self.thumbs[prediction_id] = QPixmap.fromImage(image)
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.data(Qt.UserRole)["id"] == prediction_id:
                item.setIcon(QIcon(self.thumbs[prediction_id]))

    def open_details(self, item):
        dialog = DetailsDialog(self.api, item.data(Qt.UserRole), self)
        if dialog.exec() == DetailsDialog.DELETED:
            self.records = [r for r in self.records if r["id"] != dialog.record["id"]]
            self.render()


class DetailsDialog(QDialog):
    DELETED = 2

    def __init__(self, api, record, parent):
        super().__init__(parent)
        self.api, self.record = api, record
        self.setWindowTitle("Prediction details")
        self.resize(860, 520)

        self.image = QLabel("Loading image...")
        self.image.setAlignment(Qt.AlignCenter)
        self.image.setMinimumSize(400, 400)
        self.full_image = None

        prediction = PredictionView()
        prediction.set_result(record)
        text = QPlainTextEdit(
            "Metadata (sent by the client)\n"
            + json.dumps(record["metadata"], indent=2)
            + "\n\nStored image (GridFS)\n"
            + json.dumps({"imageId": record["imageId"], **record["image"]}, indent=2))
        text.setReadOnly(True)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.delete_button)
        buttons.addWidget(close)
        buttons.addStretch()

        right = QVBoxLayout()
        right.addWidget(prediction)
        right.addWidget(text, 1)
        right.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(self.image, 1)
        layout.addLayout(right, 1)

        run_async(lambda: QImage.fromData(api.image(record["imageUrl"])), self.on_image, self.on_error)

    def on_image(self, _, image):
        self.full_image = QPixmap.fromImage(image)
        self.fit_image()

    def on_error(self, _, message):
        self.image.setText(message)

    def fit_image(self):
        if self.full_image:
            self.image.setPixmap(self.full_image.scaled(self.image.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_image()

    def delete(self):
        answer = QMessageBox.question(self, "Delete", "Delete this prediction and its image from MongoDB?")
        if answer != QMessageBox.Yes:
            return
        self.delete_button.setEnabled(False)
        run_async(lambda: self.api.delete(self.record["id"]), self.on_deleted, self.on_error_delete)

    def on_deleted(self, *_):
        self.done(self.DELETED)

    def on_error_delete(self, _, message):
        self.delete_button.setEnabled(True)
        QMessageBox.warning(self, "Delete", message)
