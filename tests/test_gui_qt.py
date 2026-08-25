import numpy as np
from PySide6.QtCore import QPointF

from config.loader import load_tasks_config
from i18n import t
from gui_qt.widgets.alerts_panel import AlertsPanel
from gui_qt.widgets.calibration_view import CalibrationView
from gui_qt.widgets.camera_grid import CameraGrid
from gui_qt.widgets.camera_tile import CameraTile
from gui_qt.widgets.settings_panel import SettingsPanel
from notify.flag import Flag
from vision.types import Track

TASKS_YAML = """\
cameras:
  cam1:
    tasks:
      - type: item_counting
        detect_fps: 5
        params: {}
        flags:
          - id: count_threshold
            enabled: true
            severity: warning
            notify: [log]
      - type: missing_product
        detect_fps: 3
        params:
          zones: []
        flags:
          - id: missing_product
            enabled: true
            severity: warning
            notify: [log, desktop]
"""


class _FakeCameraManager:
    def __init__(self, cameras, frames=None, connected=None):
        self._cameras = cameras
        self._frames = frames or {}
        self._connected = connected or {}

    def list_cameras(self):
        return self._cameras

    def get_frame(self, camera_id):
        return self._frames.get(camera_id)

    def is_connected(self, camera_id):
        return self._connected.get(camera_id, False)


# ---------------------------------------------------------------------- #
# CameraGrid / CameraTile
# ---------------------------------------------------------------------- #

def test_camera_grid_creates_one_tile_per_camera(qapp):
    grid = CameraGrid([("cam1", "C1"), ("cam2", "C2")])

    assert set(grid.tiles.keys()) == {"cam1", "cam2"}


def test_camera_tile_handles_no_frame_without_crashing(qapp):
    tile = CameraTile("cam1", "C1")

    tile.update_frame(None, False, None)

    assert tile.status_label.text() == t("live.waiting")


def test_camera_tile_renders_frame_with_overlays(qapp):
    tile = CameraTile("cam1", "C1")
    tile.resize(200, 150)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    track = Track(class_name="person", confidence=0.9, bbox=(10, 10, 50, 50), track_id=1)

    tile.update_frame(frame, True, ([], [track]))

    assert tile.status_label.text() == t("live.connected")
    assert not tile.video_label.pixmap().isNull()


# ---------------------------------------------------------------------- #
# AlertsPanel
# ---------------------------------------------------------------------- #

def test_alerts_panel_shows_most_recent_flag_first(qapp):
    panel = AlertsPanel()
    flags = [
        Flag(camera_id="cam1", task_type="item_counting", flag_id="count_threshold",
             severity="warning", message="first", timestamp=100.0),
        Flag(camera_id="cam1", task_type="missing_product", flag_id="missing_product",
             severity="critical", message="second", timestamp=200.0),
    ]

    panel.update_flags(flags)

    assert panel.table.rowCount() == 2
    assert panel.table.item(0, 4).text() == "second"
    assert panel.table.item(1, 4).text() == "first"


def test_alerts_panel_shows_narrator_summary(qapp):
    panel = AlertsPanel()

    panel.update_summary("Summary: 2 missing-PPE alerts on camera 1.")

    assert panel.summary_text.toPlainText() == "Summary: 2 missing-PPE alerts on camera 1."


def test_alerts_panel_ignores_none_summary(qapp):
    panel = AlertsPanel()
    panel.update_summary("existing summary")

    panel.update_summary(None)  # the narrator produced nothing new this cycle

    assert panel.summary_text.toPlainText() == "existing summary"


# ---------------------------------------------------------------------- #
# CalibrationView
# ---------------------------------------------------------------------- #

def test_calibration_view_populates_combos_from_tasks_yaml(qapp, tmp_path):
    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    view = CalibrationView(camera_manager, str(tasks_path))

    assert view.camera_combo.count() == 1
    assert view.task_combo.count() == 2
    assert view.task_combo.itemText(0) == "0: item_counting"
    assert view.task_combo.itemText(1) == "1: missing_product"


def test_calibration_view_saves_counting_line(qapp, tmp_path):
    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    camera_manager = _FakeCameraManager([("cam1", "C1")], frames={"cam1": frame})

    view = CalibrationView(camera_manager, str(tasks_path))
    view.task_combo.setCurrentIndex(0)  # item_counting
    view._capture_frame()

    view._on_scene_clicked(QPointF(10, 20))
    view._on_scene_clicked(QPointF(300, 400))
    view._save()

    tasks_by_camera = load_tasks_config(str(tasks_path))
    line = tasks_by_camera["cam1"][0].params["counting_line"]
    assert line == {"p1": [10, 20], "p2": [300, 400]}


def test_calibration_view_saves_zone_polygon(qapp, tmp_path):
    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    camera_manager = _FakeCameraManager([("cam1", "C1")], frames={"cam1": frame})

    view = CalibrationView(camera_manager, str(tasks_path))
    view.task_combo.setCurrentIndex(1)  # missing_product
    view._capture_frame()
    view.zone_name_edit.setText("shelf_1")
    view.expected_class_edit.setText("bottle")

    for x, y in [(10, 10), (100, 10), (100, 100), (10, 100)]:
        view._on_scene_clicked(QPointF(x, y))
    view._save()

    tasks_by_camera = load_tasks_config(str(tasks_path))
    zones = tasks_by_camera["cam1"][1].params["zones"]
    assert len(zones) == 1
    assert zones[0]["name"] == "shelf_1"
    assert zones[0]["expected_class"] == "bottle"
    assert zones[0]["polygon"] == [[10, 10], [100, 10], [100, 100], [10, 100]]


# ---------------------------------------------------------------------- #
# SettingsPanel
# ---------------------------------------------------------------------- #

def test_settings_panel_lists_existing_tasks(qapp, tmp_path):
    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    panel = SettingsPanel(camera_manager, str(tasks_path))

    assert panel.tasks_table.rowCount() == 2
    assert panel.tasks_table.item(0, 0).text() == "item_counting"
    assert panel.tasks_table.item(1, 0).text() == "missing_product"


def test_settings_panel_add_task_appends_to_tasks_yaml(qapp, tmp_path):
    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    panel = SettingsPanel(camera_manager, str(tasks_path))
    panel.new_type_combo.setCurrentText("ppe_compliance")
    panel._add_task()

    tasks_by_camera = load_tasks_config(str(tasks_path))
    assert len(tasks_by_camera["cam1"]) == 3
    assert tasks_by_camera["cam1"][2].type == "ppe_compliance"


def test_settings_panel_save_flags_updates_flag_config(qapp, tmp_path, monkeypatch):
    # _save_flags() shows a confirmation QMessageBox — .exec() blocks waiting for a
    # click that never comes in a headless test run, so stub it out.
    monkeypatch.setattr("gui_qt.widgets.settings_panel.QMessageBox.information", lambda *a, **k: None)

    tasks_path = tmp_path / "tasks.yaml"
    tasks_path.write_text(TASKS_YAML)
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    panel = SettingsPanel(camera_manager, str(tasks_path))
    panel.tasks_table.selectRow(0)  # item_counting -> flags loaded into flags_table

    enabled_checkbox = panel.flags_table.cellWidget(0, 1)
    enabled_checkbox.setChecked(False)
    severity_combo = panel.flags_table.cellWidget(0, 2)
    severity_combo.setCurrentText("critical")

    panel._save_flags()

    tasks_by_camera = load_tasks_config(str(tasks_path))
    flag = tasks_by_camera["cam1"][0].flags[0]
    assert flag.enabled is False
    assert flag.severity == "critical"


def test_camera_tile_follows_the_configured_language(qapp):
    """The desktop GUI renders in app.yaml -> ui.language, using the same
    catalog as the web interface (src/i18n.py)."""
    tile = CameraTile("cam1", "C1", language="pt")

    tile.update_frame(None, True, None)

    assert tile.status_label.text() == t("live.connected", "pt") == "conectada"
