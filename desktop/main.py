"""Cats vs Dogs desktop client (PySide6 + OpenCV).

Run:  .venv\\Scripts\\python main.py [API_URL]
The API URL defaults to http://127.0.0.1:5000 (or the CATS_DOGS_API environment variable).
"""
import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QTabWidget, QVBoxLayout, QWidget

from api_client import ApiClient
from tabs import HistoryTab, UploadTab, WebcamTab
from workers import run_async

STYLE = """
QWidget { background: #ffffff; color: #222222; font-family: Arial; font-size: 10pt; }
QPushButton, QComboBox {
    background: #f2f2f2; border: 1px solid #999999; border-radius: 3px; padding: 4px 12px;
}
QPushButton:hover { background: #e4e4e4; }
QPushButton:disabled { color: #888888; }
QComboBox QAbstractItemView { border: 1px solid #999999; selection-background-color: #dddddd; selection-color: #222222; }
QTabWidget::pane { border: 1px solid #cccccc; }
QTabBar::tab { background: #f2f2f2; border: 1px solid #999999; padding: 5px 16px; margin-right: 4px; }
QTabBar::tab:selected { background: #333333; color: #ffffff; border-color: #333333; }
QListWidget, QPlainTextEdit { border: 1px solid #cccccc; }
QListWidget::item:selected { background: #e6e6e6; color: #222222; }
QProgressBar { border: none; background: #dddddd; }
QProgressBar::chunk { background: #444444; }
QLabel#video { background: #222222; color: #bbbbbb; }
QLabel#muted { color: #666666; }
QLabel#error { color: #cc0000; }
QWidget#panel { border: 1px solid #cccccc; }
QWidget#panel QLabel, QWidget#panel QProgressBar { border: none; }
"""


class MainWindow(QMainWindow):
    def __init__(self, api: ApiClient):
        super().__init__()
        self.api = api
        self.setWindowTitle("Cats vs Dogs")
        self.resize(1150, 720)

        title = QLabel("Cats vs Dogs Classifier")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        self.status = QLabel("Server: connecting...")

        self.upload = UploadTab(api)
        self.webcam = WebcamTab(api)
        self.history = HistoryTab(api)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.upload, "Upload")
        self.tabs.addTab(self.webcam, "Webcam")
        self.tabs.addTab(self.history, "History")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(title)
        layout.addWidget(self.status)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.check_health()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_health)
        self.timer.start(10_000)

    def check_health(self):
        run_async(self.api.health, self.on_health, self.on_health_error)

    def on_health(self, _, health):
        acc = health["model"].get("test_accuracy")
        name = health["model"].get("architecture", "MobileNetV2")  # older model_info.json has no architecture
        model = f"Model: {name} ({acc * 100:.1f}% test accuracy)" if acc else f"Model: {name}"
        db = "online" if health.get("database") else "online, database offline"
        self.status.setText(f"{model} | Server: <span style='color:green'>{db}</span> ({self.api.base_url})")

    def on_health_error(self, _, message):
        self.status.setText(f"Server: <span style='color:#cc0000'>offline</span> ({self.api.base_url}). {message}")

    def on_tab_changed(self, index):
        if self.tabs.widget(index) is self.history:
            self.history.refresh()

    def closeEvent(self, event):
        self.webcam.shutdown()  # release the camera before exiting
        super().closeEvent(event)


def main():
    api_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("CATS_DOGS_API", "http://127.0.0.1:5000")
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow(ApiClient(api_url))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
