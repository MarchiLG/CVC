"""
camera_tile.py

One camera "tile": shows the video feed of ONE camera with the most
recent detections/tracks drawn on top, plus the name and connection
status. Used in a grid by CameraGrid.

The box drawing itself lives in vision/overlay.py, shared with the
MJPEG streaming of the web UI (web/streaming.py), so both interfaces
show exactly the same overlay.
"""

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from i18n import DEFAULT_LANGUAGE, t
from vision.overlay import draw_tracks


class CameraTile(QWidget):
    def __init__(self, camera_id: str, name: str, parent=None, language: str = DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.camera_id = camera_id
        self.name = name
        self.language = language
        self._last_pixmap = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        self.title_label = QLabel(name)
        self.title_label.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background-color: black;")
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setMinimumSize(160, 90)
        layout.addWidget(self.video_label, stretch=1)

        self.status_label = QLabel(t("live.waiting", self.language))
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(self.status_label)

    def update_frame(self, frame, connected: bool, result):
        self.status_label.setText(
            t("live.connected" if connected else "live.waiting", self.language)
        )

        if frame is None:
            return

        if result is not None:
            _detections, tracks = result
            frame = draw_tracks(frame, tracks)

        self._render(frame)

    def _render(self, frame):
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        image = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        self._last_pixmap = QPixmap.fromImage(image)
        self._apply_pixmap()

    def _apply_pixmap(self):
        if self._last_pixmap is None:
            return
        scaled = self._last_pixmap.scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(scaled)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._apply_pixmap()
