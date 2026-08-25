"""
camera_tile.py

Um "azulejo" de câmera: mostra o feed de vídeo de UMA câmera com as
detecções/rastreios mais recentes desenhados por cima, além do nome e
status de conexão. Usado em grade por CameraGrid — substitui a visão
de câmera única da GUI Tkinter anterior, que só exibia uma câmera
selecionada por vez.
"""

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

BOX_COLOR = (0, 255, 0)  # BGR


class CameraTile(QWidget):
    def __init__(self, camera_id: str, name: str, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.name = name
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

        self.status_label = QLabel("aguardando conexão...")
        self.status_label.setStyleSheet("color: #aaaaaa; font-size: 10px;")
        layout.addWidget(self.status_label)

    def update_frame(self, frame, connected: bool, result):
        self.status_label.setText("conectada" if connected else "aguardando conexão...")

        if frame is None:
            return

        if result is not None:
            _detections, tracks = result
            frame = self._draw_overlays(frame, tracks)

        self._render(frame)

    def _draw_overlays(self, frame, tracks):
        if not tracks:
            return frame
        frame = frame.copy()
        for track in tracks:
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 2)
            label = f"{track.class_name} #{track.track_id} {track.confidence:.2f}"
            cv2.putText(
                frame, label, (x1, max(0, y1 - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, BOX_COLOR, 1, cv2.LINE_AA,
            )
        return frame

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
