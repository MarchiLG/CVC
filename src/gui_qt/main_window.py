"""
main_window.py

Main window (PySide6): a grid with every live camera, a docked alerts
panel, and calibration/settings/employees tabs.

The interface language comes from app.yaml -> ui.language and is
applied when the widgets are built, so changing it requires restarting
the application. The web interface, by contrast, has a language picker
that switches instantly (see web/static/js/i18n.js) — both read the
same catalog in src/i18n.py.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDockWidget, QMainWindow, QTabWidget

from i18n import DEFAULT_LANGUAGE, t

from .widgets.alerts_panel import AlertsPanel
from .widgets.calibration_view import CalibrationView
from .widgets.camera_grid import CameraGrid
from .widgets.settings_panel import SettingsPanel

try:
    from .widgets.employee_enrollment import EmployeeEnrollmentView
except ImportError:
    EmployeeEnrollmentView = None  # insightface/onnxruntime not installed

REFRESH_MS = 100


class MainWindow(QMainWindow):
    def __init__(self, camera_manager, results_store, flag_manager, tasks_yaml_path: str,
                 narrator=None, language: str = DEFAULT_LANGUAGE):
        super().__init__()
        self.camera_manager = camera_manager
        self.results_store = results_store
        self.flag_manager = flag_manager
        self.narrator = narrator
        self.language = language

        self.setWindowTitle(t("app.window_title", language))
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")

        cameras = self.camera_manager.list_cameras()

        self.camera_grid = CameraGrid(cameras, language=language)
        self.calibration_view = CalibrationView(camera_manager, tasks_yaml_path, language=language)
        self.settings_panel = SettingsPanel(camera_manager, tasks_yaml_path, language=language)

        tabs = QTabWidget()
        tabs.addTab(self.camera_grid, t("nav.live", language))
        tabs.addTab(self.calibration_view, t("nav.calibration", language))
        tabs.addTab(self.settings_panel, t("nav.settings", language))

        if EmployeeEnrollmentView is not None:
            self.employee_enrollment_view = EmployeeEnrollmentView(camera_manager, language=language)
            tabs.addTab(self.employee_enrollment_view, t("nav.employees", language))

        self.setCentralWidget(tabs)

        self.alerts_panel = AlertsPanel(language=language)
        dock = QDockWidget(t("qt.alerts_dock", language), self)
        dock.setWidget(self.alerts_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(REFRESH_MS)

    def _tick(self):
        for camera_id, _name in self.camera_manager.list_cameras():
            frame = self.camera_manager.get_frame(camera_id)
            connected = self.camera_manager.is_connected(camera_id)
            result = self.results_store.get(camera_id)
            self.camera_grid.update_camera(camera_id, frame, connected, result)

        self.alerts_panel.update_flags(self.flag_manager.recent(limit=100))

        if self.narrator is not None:
            self.alerts_panel.update_summary(self.narrator.latest_summary())
