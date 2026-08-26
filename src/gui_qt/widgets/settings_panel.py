"""
settings_panel.py

Settings panel: lists and edits the tasks assigned to each camera in
tasks.yaml (type, model, detect_fps, required PPE) and each task's flags
(enabled, severity, notification channels). Saves through
TasksYamlWriter, preserving comments/formatting. Geometry calibration
(line/zone) lives in the Calibration tab — this panel handles the rest
of each task's configuration.
"""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.writer import TasksYamlWriter
from i18n import DEFAULT_LANGUAGE, t
from tasks.registry import available_types

_SEVERITIES = ["info", "warning", "critical"]


class SettingsPanel(QWidget):
    def __init__(self, camera_manager, tasks_yaml_path: str, parent=None,
                 language: str = DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.tasks_yaml_path = tasks_yaml_path
        self.language = language
        self._tasks = []

        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        self.camera_combo = QComboBox()
        for camera_id, name in self.camera_manager.list_cameras():
            self.camera_combo.addItem(f"{name} ({camera_id})", camera_id)
        self.camera_combo.currentIndexChanged.connect(self._reload_tasks)
        top.addWidget(QLabel(t("calib.camera", language) + ":"))
        top.addWidget(self.camera_combo)
        layout.addLayout(top)

        layout.addWidget(QLabel(t("qt.tasks_label", language)))
        self.tasks_table = QTableWidget(0, 5)
        self.tasks_table.setHorizontalHeaderLabels([
            t("qt.col.type", language),
            t("qt.col.model", language),
            t("settings.detect_fps", language),
            t("qt.col.required_ppe", language),
            t("qt.col.remove", language),
        ])
        self.tasks_table.itemSelectionChanged.connect(self._on_task_selected)
        layout.addWidget(self.tasks_table)

        add_row = QHBoxLayout()
        self.new_type_combo = QComboBox()
        self.new_type_combo.addItems(available_types())
        add_row.addWidget(QLabel(t("qt.new_task", language)))
        add_row.addWidget(self.new_type_combo)
        add_task_btn = QPushButton(t("settings.add", language))
        add_task_btn.clicked.connect(self._add_task)
        add_row.addWidget(add_task_btn)
        save_tasks_btn = QPushButton(t("qt.save_tasks", language))
        save_tasks_btn.clicked.connect(self._save_tasks)
        add_row.addWidget(save_tasks_btn)
        layout.addLayout(add_row)

        layout.addWidget(QLabel(t("qt.flags_label", language)))
        self.flags_table = QTableWidget(0, 4)
        self.flags_table.setHorizontalHeaderLabels([
            t("qt.col.id", language),
            t("qt.col.enabled", language),
            t("qt.col.severity", language),
            t("qt.col.notify", language),
        ])
        layout.addWidget(self.flags_table)

        save_flags_btn = QPushButton(t("qt.save_flags", language))
        save_flags_btn.clicked.connect(self._save_flags)
        layout.addWidget(save_flags_btn)

        if self.camera_combo.count() > 0:
            self._reload_tasks()

    # ------------------------------------------------------------------ #
    def _selected_camera_id(self):
        return self.camera_combo.currentData()

    def _reload_tasks(self):
        camera_id = self._selected_camera_id()
        writer = TasksYamlWriter(self.tasks_yaml_path)
        self._tasks = list(writer.get_tasks(camera_id)) if camera_id else []

        self.tasks_table.setRowCount(len(self._tasks))
        for row, task in enumerate(self._tasks):
            self.tasks_table.setItem(row, 0, QTableWidgetItem(str(task.get("type", ""))))
            self.tasks_table.setItem(row, 1, QTableWidgetItem(str(task.get("model") or "")))

            fps_spin = QDoubleSpinBox()
            fps_spin.setRange(0.1, 30.0)
            fps_spin.setValue(float(task.get("detect_fps", 5.0)))
            self.tasks_table.setCellWidget(row, 2, fps_spin)

            required_ppe = ",".join(task.get("params", {}).get("required_ppe", []))
            self.tasks_table.setItem(row, 3, QTableWidgetItem(required_ppe))

            remove_btn = QPushButton(t("settings.remove", self.language))
            remove_btn.clicked.connect(lambda _checked, r=row: self._remove_task(r))
            self.tasks_table.setCellWidget(row, 4, remove_btn)

        self.flags_table.setRowCount(0)

    def _on_task_selected(self):
        rows = {index.row() for index in self.tasks_table.selectedIndexes()}
        if not rows:
            self.flags_table.setRowCount(0)
            return
        row = next(iter(rows))
        if row >= len(self._tasks):
            return
        flags = self._tasks[row].get("flags", [])

        self.flags_table.setRowCount(len(flags))
        for i, flag in enumerate(flags):
            self.flags_table.setItem(i, 0, QTableWidgetItem(str(flag.get("id", ""))))

            enabled_checkbox = QCheckBox()
            enabled_checkbox.setChecked(bool(flag.get("enabled", True)))
            self.flags_table.setCellWidget(i, 1, enabled_checkbox)

            severity_combo = QComboBox()
            severity_combo.addItems(_SEVERITIES)
            current_severity = flag.get("severity", "info")
            if current_severity in _SEVERITIES:
                severity_combo.setCurrentText(current_severity)
            self.flags_table.setCellWidget(i, 2, severity_combo)

            notify_str = ",".join(flag.get("notify", []))
            self.flags_table.setItem(i, 3, QTableWidgetItem(notify_str))

    # ------------------------------------------------------------------ #
    def _add_task(self):
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        task_type = self.new_type_combo.currentText()
        writer = TasksYamlWriter(self.tasks_yaml_path)
        writer.add_task(camera_id, task_type)
        self._reload_tasks()

    def _remove_task(self, row: int):
        camera_id = self._selected_camera_id()
        if camera_id is None or row >= len(self._tasks):
            return
        confirm = QMessageBox.question(
            self,
            t("qt.remove_task_title", self.language),
            t("qt.remove_task_question", self.language),
        )
        if confirm != QMessageBox.Yes:
            return
        writer = TasksYamlWriter(self.tasks_yaml_path)
        writer.remove_task(camera_id, row)
        self._reload_tasks()

    def _save_tasks(self):
        camera_id = self._selected_camera_id()
        if camera_id is None:
            return
        writer = TasksYamlWriter(self.tasks_yaml_path)
        for row, task in enumerate(self._tasks):
            fps_spin = self.tasks_table.cellWidget(row, 2)
            writer.set_task_detect_fps(camera_id, row, fps_spin.value())

            if task.get("type") == "ppe_compliance":
                required_ppe_item = self.tasks_table.item(row, 3)
                required_ppe_text = required_ppe_item.text().strip() if required_ppe_item else ""
                params = dict(task.get("params", {}) or {})
                params["required_ppe"] = [c.strip() for c in required_ppe_text.split(",") if c.strip()]
                writer.set_task_params(camera_id, row, params)

        self._reload_tasks()
        QMessageBox.information(
            self, t("qt.saved_title", self.language), t("qt.tasks_saved", self.language)
        )

    def _save_flags(self):
        camera_id = self._selected_camera_id()
        rows = {index.row() for index in self.tasks_table.selectedIndexes()}
        if camera_id is None or not rows:
            return
        task_row = next(iter(rows))

        writer = TasksYamlWriter(self.tasks_yaml_path)
        for i in range(self.flags_table.rowCount()):
            flag_id = self.flags_table.item(i, 0).text()
            enabled = self.flags_table.cellWidget(i, 1).isChecked()
            severity = self.flags_table.cellWidget(i, 2).currentText()
            notify_item = self.flags_table.item(i, 3)
            notify = [c.strip() for c in (notify_item.text() if notify_item else "").split(",") if c.strip()]
            writer.set_flag(camera_id, task_row, flag_id, enabled=enabled, severity=severity, notify=notify)

        QMessageBox.information(
            self, t("qt.saved_title", self.language), t("qt.flags_saved", self.language)
        )
