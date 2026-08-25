"""
calibration_view.py

Tela de calibração: congela o frame mais recente de uma câmera,
permite desenhar (clicando) a linha de contagem (item_counting) ou o
polígono de uma zona (ppe_compliance / missing_product) sobre a
imagem em resolução nativa, e salva de volta em tasks.yaml via
TasksYamlWriter — preservando comentários/formatação do arquivo.

A imagem é exibida em resolução nativa (sem escalar para caber na
tela) para que as coordenadas clicadas correspondam exatamente aos
pixels do frame — o mesmo sistema de coordenadas usado por
counting_line/zones em tasks.yaml.
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

from config.writer import TasksYamlWriter

_LINE_TYPES = {"item_counting"}
_ZONE_TYPES = {"ppe_compliance", "missing_product"}
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
    def __init__(self, camera_manager, tasks_yaml_path: str, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.tasks_yaml_path = tasks_yaml_path
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
        controls.addWidget(QLabel("Câmera:"))
        controls.addWidget(self.camera_combo)

        self.task_combo = QComboBox()
        self.task_combo.currentIndexChanged.connect(self._on_task_changed)
        controls.addWidget(QLabel("Tarefa:"))
        controls.addWidget(self.task_combo)

        self.zone_name_edit = QLineEdit()
        self.zone_name_edit.setPlaceholderText("nome da zona")
        controls.addWidget(self.zone_name_edit)

        self.expected_class_edit = QLineEdit()
        self.expected_class_edit.setPlaceholderText("classe esperada (missing_product)")
        controls.addWidget(self.expected_class_edit)

        capture_btn = QPushButton("Capturar frame atual")
        capture_btn.clicked.connect(self._capture_frame)
        controls.addWidget(capture_btn)

        clear_btn = QPushButton("Limpar pontos")
        clear_btn.clicked.connect(self._clear_points)
        controls.addWidget(clear_btn)

        finish_btn = QPushButton("Finalizar polígono")
        finish_btn.clicked.connect(self._finish_polygon)
        controls.addWidget(finish_btn)

        save_btn = QPushButton("Salvar")
        save_btn.clicked.connect(self._save)
        controls.addWidget(save_btn)

        layout.addLayout(controls)

        self.status_label = QLabel("Selecione uma câmera e uma tarefa, depois capture um frame.")
        layout.addWidget(self.status_label)

        self.scene = _ClickableScene(self._on_scene_clicked)
        self.view = QGraphicsView(self.scene)
        layout.addWidget(self.view, stretch=1)

        if self.camera_combo.count() > 0:
            self._on_camera_changed(0)

    # ------------------------------------------------------------------ #
    # Seleção de câmera / tarefa
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
        self.status_label.setText(f"Tarefa selecionada: {task_type}")

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
    # Captura de frame / desenho
    # ------------------------------------------------------------------ #
    def _capture_frame(self):
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        frame = self.camera_manager.get_frame(camera_id)
        if frame is None:
            QMessageBox.warning(self, "Sem frame", "Ainda não há frame disponível para esta câmera.")
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
        self.status_label.setText(f"Frame capturado ({w}x{h}). Clique para marcar pontos.")

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
        self.status_label.setText(f"Polígono com {len(self._points)} pontos pronto para salvar.")

    def _clear_points(self):
        for item in self._point_items:
            self.scene.removeItem(item)
        self._point_items = []
        if self._shape_item is not None:
            self.scene.removeItem(self._shape_item)
            self._shape_item = None
        self._points = []

    # ------------------------------------------------------------------ #
    # Salvar
    # ------------------------------------------------------------------ #
    def _save(self):
        camera_id = self._selected_camera_id()
        task_index = self._selected_task_index()
        task = self._selected_task()
        if camera_id is None or task_index is None or task is None:
            return

        task_type = task.get("type")
        params = dict(task.get("params", {}) or {})

        if task_type in _LINE_TYPES:
            if len(self._points) != 2:
                QMessageBox.warning(self, "Linha incompleta", "Marque exatamente 2 pontos para a linha de contagem.")
                return
            (x1, y1), (x2, y2) = self._points
            params["counting_line"] = {"p1": [round(x1), round(y1)], "p2": [round(x2), round(y2)]}

        elif task_type in _ZONE_TYPES:
            if len(self._points) < 3:
                QMessageBox.warning(self, "Zona incompleta", "Marque pelo menos 3 pontos para a zona.")
                return
            name = self.zone_name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, "Nome obrigatório", "Informe um nome para a zona.")
                return

            zone = {"name": name, "polygon": [[round(x), round(y)] for x, y in self._points]}
            if task_type == "missing_product":
                expected_class = self.expected_class_edit.text().strip()
                if not expected_class:
                    QMessageBox.warning(self, "Classe obrigatória", "Informe a classe esperada da zona.")
                    return
                zone["expected_class"] = expected_class

            zones = list(params.get("zones", []))
            for i, existing in enumerate(zones):
                if existing.get("name") == name:
                    zones[i] = zone
                    break
            else:
                zones.append(zone)
            params["zones"] = zones

        else:
            QMessageBox.warning(self, "Tipo não suportado", f"Calibração visual não suportada para '{task_type}'.")
            return

        writer = TasksYamlWriter(self.tasks_yaml_path)
        writer.set_task_params(camera_id, task_index, params)
        self._current_tasks = self._load_tasks(camera_id)
        self.status_label.setText("Salvo em tasks.yaml.")
