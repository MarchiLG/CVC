from types import SimpleNamespace

import numpy as np

from db import repository
from db.session import get_session, init_db
from gui_qt.widgets.employee_enrollment import EmployeeEnrollmentView


class _FakeCameraManager:
    def __init__(self, cameras, frames=None):
        self._cameras = cameras
        self._frames = frames or {}

    def list_cameras(self):
        return self._cameras

    def get_frame(self, camera_id):
        return self._frames.get(camera_id)


class _FakeRecognizer:
    def __init__(self, faces):
        self._faces = faces

    def analyze(self, frame):
        return self._faces


def _fake_face(embedding, det_score=0.9):
    return SimpleNamespace(embedding=np.asarray(embedding, dtype=np.float32), det_score=det_score)


def test_enrollment_view_lists_no_employees_initially(qapp, tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    view = EmployeeEnrollmentView(camera_manager)

    assert view.employee_list.count() == 0


def test_capture_and_enroll_creates_employee(qapp, tmp_path, monkeypatch):
    init_db(f"sqlite:///{tmp_path}/test.db")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    camera_manager = _FakeCameraManager([("cam1", "C1")], frames={"cam1": frame})

    import gui_qt.widgets.employee_enrollment as mod
    monkeypatch.setattr(mod, "get_face_recognizer", lambda model_pack: _FakeRecognizer([_fake_face([1.0, 0.0])]))

    view = EmployeeEnrollmentView(camera_manager)
    view._capture_from_camera()
    view.name_edit.setText("Alice")
    view._enroll()

    session = get_session()
    employees = repository.list_employees(session)
    session.close()

    assert len(employees) == 1
    assert employees[0].name == "Alice"
    assert view.employee_list.count() == 1
    assert view.name_edit.text() == ""  # cleared after successful enrollment


def test_enroll_without_photo_shows_warning_and_creates_no_employee(qapp, tmp_path, monkeypatch):
    init_db(f"sqlite:///{tmp_path}/test.db")
    camera_manager = _FakeCameraManager([("cam1", "C1")])

    warnings = []
    monkeypatch.setattr(
        "gui_qt.widgets.employee_enrollment.QMessageBox.warning",
        lambda *a, **k: warnings.append(a),
    )

    view = EmployeeEnrollmentView(camera_manager)
    view.name_edit.setText("Alice")
    view._enroll()

    session = get_session()
    employees = repository.list_employees(session)
    session.close()

    assert len(warnings) == 1
    assert employees == []


def test_enroll_without_detected_face_shows_warning(qapp, tmp_path, monkeypatch):
    init_db(f"sqlite:///{tmp_path}/test.db")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    camera_manager = _FakeCameraManager([("cam1", "C1")], frames={"cam1": frame})

    import gui_qt.widgets.employee_enrollment as mod
    monkeypatch.setattr(mod, "get_face_recognizer", lambda model_pack: _FakeRecognizer([]))  # no faces found

    warnings = []
    monkeypatch.setattr(
        "gui_qt.widgets.employee_enrollment.QMessageBox.warning",
        lambda *a, **k: warnings.append(a),
    )

    view = EmployeeEnrollmentView(camera_manager)
    view._capture_from_camera()
    view.name_edit.setText("Alice")
    view._enroll()

    session = get_session()
    employees = repository.list_employees(session)
    session.close()

    assert len(warnings) == 1
    assert employees == []
