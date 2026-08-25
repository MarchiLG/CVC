"""
main_window.py

Janela principal (PySide6): grade com todas as câmeras ao vivo, um
painel de alertas ancorado, e abas de calibração/configurações/
funcionários — a versão fase 4 substitui a GUI Tkinter (que só exibia
uma câmera selecionada por vez, sem calibração/configurações) por
esta interface.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QDockWidget, QMainWindow, QTabWidget

from .widgets.alerts_panel import AlertsPanel
from .widgets.calibration_view import CalibrationView
from .widgets.camera_grid import CameraGrid
from .widgets.settings_panel import SettingsPanel

try:
    from .widgets.employee_enrollment import EmployeeEnrollmentView
except ImportError:
    EmployeeEnrollmentView = None  # insightface/onnxruntime não instalados

REFRESH_MS = 100


class MainWindow(QMainWindow):
    def __init__(self, camera_manager, results_store, flag_manager, tasks_yaml_path: str, narrator=None):
        super().__init__()
        self.camera_manager = camera_manager
        self.results_store = results_store
        self.flag_manager = flag_manager
        self.narrator = narrator

        self.setWindowTitle("Computer Vision Central")
        self.resize(1400, 900)
        self.setStyleSheet("background-color: #1e1e1e; color: white;")

        cameras = self.camera_manager.list_cameras()

        self.camera_grid = CameraGrid(cameras)
        self.calibration_view = CalibrationView(camera_manager, tasks_yaml_path)
        self.settings_panel = SettingsPanel(camera_manager, tasks_yaml_path)

        tabs = QTabWidget()
        tabs.addTab(self.camera_grid, "Ao vivo")
        tabs.addTab(self.calibration_view, "Calibração")
        tabs.addTab(self.settings_panel, "Configurações")

        if EmployeeEnrollmentView is not None:
            self.employee_enrollment_view = EmployeeEnrollmentView(camera_manager)
            tabs.addTab(self.employee_enrollment_view, "Funcionários")

        self.setCentralWidget(tabs)

        self.alerts_panel = AlertsPanel()
        dock = QDockWidget("Alertas", self)
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
