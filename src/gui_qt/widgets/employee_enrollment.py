"""
employee_enrollment.py

Tela de cadastro de funcionários: captura o frame atual de uma câmera
(ou carrega um arquivo de imagem), extrai o embedding facial via
InsightFace (mesmo pacote de modelo do device — buffalo_l/buffalo_s,
ver vision/device.py) e salva funcionário + embedding no banco.
"""

import cv2
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from db import repository
from db.session import get_session
from vision.device import default_face_model_for_device, resolve_device
from vision.face.recognizer import get_face_recognizer


class EmployeeEnrollmentView(QWidget):
    def __init__(self, camera_manager, parent=None):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self._current_frame = None
        self._recognizer = None

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.camera_combo = QComboBox()
        for camera_id, name in self.camera_manager.list_cameras():
            self.camera_combo.addItem(f"{name} ({camera_id})", camera_id)
        controls.addWidget(QLabel("Câmera:"))
        controls.addWidget(self.camera_combo)

        capture_btn = QPushButton("Capturar da câmera")
        capture_btn.clicked.connect(self._capture_from_camera)
        controls.addWidget(capture_btn)

        upload_btn = QPushButton("Carregar foto...")
        upload_btn.clicked.connect(self._load_from_file)
        controls.addWidget(upload_btn)
        layout.addLayout(controls)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(320, 240)
        self.preview_label.setStyleSheet("background-color: black;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)

        self.status_label = QLabel("Capture ou carregue uma foto com um rosto visível.")
        layout.addWidget(self.status_label)

        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nome do funcionário")
        name_row.addWidget(QLabel("Nome:"))
        name_row.addWidget(self.name_edit)
        enroll_btn = QPushButton("Cadastrar")
        enroll_btn.clicked.connect(self._enroll)
        name_row.addWidget(enroll_btn)
        layout.addLayout(name_row)

        layout.addWidget(QLabel("Funcionários cadastrados"))
        self.employee_list = QListWidget()
        layout.addWidget(self.employee_list)

        self._refresh_employee_list()

    # ------------------------------------------------------------------ #
    def _get_recognizer(self):
        if self._recognizer is None:
            device = resolve_device("auto")
            model_pack = default_face_model_for_device(device)
            self._recognizer = get_face_recognizer(model_pack)
        return self._recognizer

    def _capture_from_camera(self):
        camera_id = self.camera_combo.currentData()
        if camera_id is None:
            return
        frame = self.camera_manager.get_frame(camera_id)
        if frame is None:
            QMessageBox.warning(self, "Sem frame", "Ainda não há frame disponível para esta câmera.")
            return
        self._set_frame(frame)

    def _load_from_file(self):
        path, _filter = QFileDialog.getOpenFileName(self, "Selecionar foto", "", "Imagens (*.png *.jpg *.jpeg)")
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.warning(self, "Erro", "Não foi possível abrir a imagem selecionada.")
            return
        self._set_frame(frame)

    def _set_frame(self, frame):
        self._current_frame = frame
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = frame_rgb.shape
        image = QImage(frame_rgb.data, w, h, ch * w, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pixmap)
        self.status_label.setText("Foto carregada. Informe o nome e clique em Cadastrar.")

    # ------------------------------------------------------------------ #
    def _enroll(self):
        if self._current_frame is None:
            QMessageBox.warning(self, "Sem foto", "Capture ou carregue uma foto primeiro.")
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Nome obrigatório", "Informe o nome do funcionário.")
            return

        faces = self._get_recognizer().analyze(self._current_frame)
        if not faces:
            QMessageBox.warning(self, "Nenhum rosto encontrado", "Não foi possível detectar um rosto na foto.")
            return
        face = max(faces, key=lambda f: f.det_score)

        session = get_session()
        try:
            employee = repository.add_employee(session, name)
            repository.add_face_embedding(session, employee.id, face.embedding)
        finally:
            session.close()

        self.status_label.setText(f"Funcionário '{name}' cadastrado.")
        self.name_edit.clear()
        self._current_frame = None
        self.preview_label.clear()
        self._refresh_employee_list()

    def _refresh_employee_list(self):
        self.employee_list.clear()
        session = get_session()
        try:
            for employee in repository.list_employees(session):
                self.employee_list.addItem(f"{employee.id}: {employee.name}")
        finally:
            session.close()
