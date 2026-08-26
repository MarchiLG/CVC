"""
employee_enrollment.py

Employee enrollment screen: captures the current frame of a camera (or
loads an image file), extracts the face embedding through InsightFace
(the same model pack chosen for the device — buffalo_l/buffalo_s, see
vision/device.py) and stores employee + embedding in the database.
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
from i18n import DEFAULT_LANGUAGE, t
from vision.device import default_face_model_for_device, resolve_device
from vision.face.recognizer import get_face_recognizer


class EmployeeEnrollmentView(QWidget):
    def __init__(self, camera_manager, parent=None, language: str = DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.camera_manager = camera_manager
        self.language = language
        self._current_frame = None
        self._recognizer = None

        layout = QVBoxLayout(self)

        controls = QHBoxLayout()
        self.camera_combo = QComboBox()
        for camera_id, name in self.camera_manager.list_cameras():
            self.camera_combo.addItem(f"{name} ({camera_id})", camera_id)
        controls.addWidget(QLabel(t("calib.camera", language) + ":"))
        controls.addWidget(self.camera_combo)

        capture_btn = QPushButton(t("emp.capture_from", language))
        capture_btn.clicked.connect(self._capture_from_camera)
        controls.addWidget(capture_btn)

        upload_btn = QPushButton(t("qt.load_photo", language))
        upload_btn.clicked.connect(self._load_from_file)
        controls.addWidget(upload_btn)
        layout.addLayout(controls)

        self.preview_label = QLabel()
        self.preview_label.setFixedSize(320, 240)
        self.preview_label.setStyleSheet("background-color: black;")
        self.preview_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.preview_label)

        self.status_label = QLabel(t("qt.enroll_hint", language))
        layout.addWidget(self.status_label)

        name_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText(t("emp.name_placeholder", language))
        name_row.addWidget(QLabel(t("emp.name", language) + ":"))
        name_row.addWidget(self.name_edit)
        enroll_btn = QPushButton(t("emp.enroll", language))
        enroll_btn.clicked.connect(self._enroll)
        name_row.addWidget(enroll_btn)
        layout.addLayout(name_row)

        layout.addWidget(QLabel(t("emp.list_title", language)))
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
            QMessageBox.warning(
                self, t("qt.no_frame_title", self.language), t("api.no_frame", self.language)
            )
            return
        self._set_frame(frame)

    def _load_from_file(self):
        path, _filter = QFileDialog.getOpenFileName(
            self, t("qt.select_photo", self.language), "", t("qt.images_filter", self.language)
        )
        if not path:
            return
        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.warning(
                self, t("qt.error", self.language), t("qt.image_open_failed", self.language)
            )
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
        self.status_label.setText(t("qt.photo_loaded", self.language))

    # ------------------------------------------------------------------ #
    def _enroll(self):
        if self._current_frame is None:
            QMessageBox.warning(
                self, t("qt.no_photo_title", self.language), t("qt.no_photo", self.language)
            )
            return
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, t("emp.name", self.language), t("emp.name_required", self.language)
            )
            return

        faces = self._get_recognizer().analyze(self._current_frame)
        if not faces:
            QMessageBox.warning(
                self, t("qt.no_face_title", self.language), t("api.face_not_detected", self.language)
            )
            return
        face = max(faces, key=lambda f: f.det_score)

        session = get_session()
        try:
            employee = repository.add_employee(session, name)
            repository.add_face_embedding(session, employee.id, face.embedding)
        finally:
            session.close()

        self.status_label.setText(t("qt.enrolled", self.language, name=name))
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
