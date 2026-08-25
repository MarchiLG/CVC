"""
calibration_view.py

Calibration screen: freezes the most recent frame of a camera, lets you
draw (by clicking) the counting line (item_counting) or a zone polygon
(ppe_compliance / missing_product) over the image at native resolution,
and saves it back to tasks.yaml through TasksYamlWriter — preserving
the file's comments/formatting.

The image is shown at native resolution (not scaled to fit the screen)
so the clicked coordinates match the frame pixels exactly — the same
coordinate system used by counting_line/zones in tasks.yaml.

The validation/assembly rules for the geometry live in
config/calibration.py, shared with the web UI (web/api.py) — only the
Qt drawing and the QMessageBox error display live here.
"""

import cv2
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import (
    QComboBox,
    QGraphicsEllipseItem,
    QGraphicsLineItem,
    QGraphicsPixmapItem,
    QGraphicsPolygonItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from config.calibration import (
    LINE_TYPES as _LINE_TYPES,
    ZONE_TYPES as _ZONE_TYPES,
    CalibrationError,
    build_geometry_params,
)
from config.writer import TasksYamlWriter
from i18n import DEFAULT_LANGUAGE, t

POINT_COLOR = QColor("#2ecc71")
SHAPE_COLOR = QColor("#e74c3c")


class _ClickableScene(QGraphicsScene):
    def __init__(self, on_click, parent=None):
        super().__init__(parent)
        self._on_click = on_click

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click(event.scenePos())
        super().mousePressEvent(event)


class CalibrationView(QWidget):
    def __init__(self, camera_manager, tasks_yaml_path: str, parent=None,
                 language: str = DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.tasks_yaml_path = tasks_yaml_path
        self.language = language
        self._points: list[tuple[float, float]] = []
        self._point_items = []
        self._shape_item = None
        self._pixmap_item = None
        self._current_tasks = []

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.camera_combo = QComboBox()
        for camera_id, name in self.camera_manager.list_cameras():
            self.camera_combo.addItem(f"{name} ({camera_id})", camera_id)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        controls.addWidget(QLabel(t("calib.camera", language) + ":"))
        controls.addWidget(self.camera_combo)

        self.task_combo = QComboBox()
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        controls.addWidget(QLabel(t("calib.task", language) + ":"))
        controls.addWidget(self.task_combo)

        self.zone_name_edit = QLineEdit()
        self.zone_name_edit.setPlaceholderText(t("calib.zone_name", language).lower())
        controls.addWidget(self.zone_name_edit)

        self.expected_class_edit = QLineEdit()
        self.expected_class_edit.setPlaceholderText(t("calib.expected_class", language).lower())
        controls.addWidget(self.expected_class_edit)

        capture_btn = QPushButton(t("calib.capture", language))
        capture_btn.clicked.connect(self._capture_frame)
        controls.addWidget(capture_btn)

        clear_btn = QPushButton(t("calib.clear", language))
        clear_btn.clicked.connect(self._clear_points)
        controls.addWidget(clear_btn)

        finish_btn = QPushButton(t("qt.finish_polygon", language))
        finish_btn.clicked.connect(self._finish_polygon)
        controls.addWidget(finish_btn)

        save_btn = QPushButton(t("calib.save", language))
        save_btn.clicked.connect(self._save)
        controls.addWidget(save_btn)

        layout.addLayout(controls)

        self.status_label = QLabel(t("calib.hint.start", language))
        layout.addWidget(self.status_label)

        self.scene = _ClickableScene(self._on_scene_clicked)
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view, stretch=1)

        if self.camera_combo.count() > 0:
            self._on_camera_changed(0)

    # ------------------------------------------------------------------ #
    # Camera / task selection
    # ------------------------------------------------------------------ #
    def _on_camera_changed(self, _index):
        camera_id = self.camera_combo.currentData()
        self._current_tasks = self._load_tasks(camera_id)
        self.task_combo.blockSignals(True)
        self.task_combo.clear()
        for i, task in enumerate(self._current_tasks):
            self.task_combo.addItem(f"{i}: {task.get('type')}", i)
        self.task_combo.blockSignals(False)
        if self.task_combo.count() > 0:
            self._on_task_changed(0)

    def _load_tasks(self, camera_id):
        if camera_id is None:
            return []
        writer = TasksYamlWriter(self.tasks_yaml_path)
        return list(writer.get_tasks(camera_id))

    def _on_task_changed(self, _index):
        self._clear_points()
        task = self._selected_task()
        if task is None:
            return
        task_type = task.get("type")
        is_zone = task_type in _ZONE_TYPES
        self.zone_name_edit.setEnabled(is_zone)
        self.expected_class_edit.setEnabled(task_type == "missing_product")
        if is_zone:
            zones = task.get("params", {}).get("zones", [])
            if zones:
                self.zone_name_edit.setText(zones[0].get("name", ""))
                self.expected_class_edit.setText(zones[0].get("expected_class", ""))
            else:
                self.zone_name_edit.clear()
                self.expected_class_edit.clear()
        self.status_label.setText(t("qt.task_selected", self.language, type=task_type))

    def _selected_camera_id(self):
        return self.camera_combo.currentData()

    def _selected_task_index(self):
        return self.task_combo.currentData()

    def _selected_task(self):
        index = self._selected_task_index()
        if index is None or index >= len(self._current_tasks):
            return None
        return self._current_tasks[index]

    # ------------------------------------------------------------------ #
    # Frame capture / drawing
    # ------------------------------------------------------------------ #
    def _capture_frame(self):
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        frame = self.camera_manager.get_frame(camera_id)
        if frame is None:
            QMessageBox.warning(
                self, t("qt.no_frame_title", self.language), t("api.no_frame", self.language)
            )
            return

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        image = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)

        self.scene.clear()
        self._pixmap_item = QGraphicsPixmapItem(pixmap)
        self.scene.addItem(self._pixmap_item)
        self.scene.setSceneRect(0, 0, w, h)
        self._points = []
        self._point_items = []
        self._shape_item = None
        self.status_label.setText(t("calib.hint.captured", self.language, width=w, height=h))

    def _on_scene_clicked(self, scene_pos: QPointF):
        if self._pixmap_item is None:
            return
        task = self._selected_task()
        if task is None:
            return

        x, y = scene_pos.x(), scene_pos.y()

        if task.get("type") in _LINE_TYPES and len(self._points) >= 2:
            self._clear_points()

        self._points.append((x, y))
        dot = QGraphicsEllipseItem(x - 4, y - 4, 8, 8)
        dot.setBrush(QBrush(POINT_COLOR))
        dot.setPen(QPen(Qt.NoPen))
        self.scene.addItem(dot)
        self._point_items.append(dot)

        self._redraw_shape()

    def _redraw_shape(self):
        if self._shape_item is not None:
            self.scene.removeItem(self._shape_item)
            self._shape_item = None

        task = self._selected_task()
        if task is None or len(self._points) < 2:
            return

        if task.get("type") in _LINE_TYPES:
            (x1, y1), (x2, y2) = self._points[0], self._points[1]
            self._shape_item = QGraphicsLineItem(x1, y1, x2, y2)
            self._shape_item.setPen(QPen(SHAPE_COLOR, 2))
        else:
            polygon = QPolygonF([QPointF(x, y) for x, y in self._points])
            self._shape_item = QGraphicsPolygonItem(polygon)
            self._shape_item.setPen(QPen(SHAPE_COLOR, 2))
        self.scene.addItem(self._shape_item)

    def _finish_polygon(self):
        self._redraw_shape()
        self.status_label.setText(
            t("qt.polygon_ready", self.language, count=len(self._points))
        )

    def _clear_points(self):
        for item in self._point_items:
            self.scene.removeItem(item)
        self._point_items = []
        if self._shape_item is not None:
            self.scene.removeItem(self._shape_item)
            self._shape_item = None
        self._points = []

    # ------------------------------------------------------------------ #
    # Saving
    # ------------------------------------------------------------------ #
    def _save(self):
        camera_id = self._selected_camera_id()
        task_index = self._selected_task_index()
        task = self._selected_task()
        if camera_id is None or task_index is None or task is None:
            return

        try:
            params = build_geometry_params(
                task.get("type"),
                task.get("params"),
                self._points,
                zone_name=self.zone_name_edit.text(),
                expected_class=self.expected_class_edit.text(),
            )
        except CalibrationError as error:
            # The exception carries a translation code, so the message
            # follows app.yaml -> ui.language just like the rest of the UI.
            QMessageBox.warning(
                self,
                t("qt.invalid_calibration", self.language),
                t(error.code, self.language),
            )
            return

        writer = TasksYamlWriter(self.tasks_yaml_path)
        writer.set_task_params(camera_id, task_index, params)
        self._current_tasks = self._load_tasks(camera_id)
        self.status_label.setText(t("qt.saved_to_yaml", self.language))
