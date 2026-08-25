from types import SimpleNamespace

import numpy as np
import pytest

from config.schema import FlagConfig, TaskConfig
from db import repository
from db.session import get_session, init_db
from tasks.face_id import FaceIDAnalyzer


def _fake_face(embedding, det_score=0.9):
    return SimpleNamespace(embedding=np.asarray(embedding, dtype=np.float32), det_score=det_score)


class _FakeRecognizer:
    def __init__(self, faces):
        self._faces = faces

    def analyze(self, frame):
        return self._faces


def _config(**params):
    return TaskConfig(type="face_id", params=params, flags=[
        FlagConfig(id="unknown_face", enabled=True, severity="info", notify=["log"]),
    ])


@pytest.fixture(autouse=True)
def _temp_db(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")


def _make_analyzer(monkeypatch, faces, **params):
    import tasks.face_id as mod
    monkeypatch.setattr(mod, "get_face_recognizer", lambda model_pack: _FakeRecognizer(faces))
    return FaceIDAnalyzer("cam1", _config(**params))


def test_unknown_face_emits_flag_when_no_employees_registered(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, [_fake_face([1.0, 0.0, 0.0])])

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert len(flags) == 1
    assert flags[0].flag_id == "unknown_face"
    assert flags[0].camera_id == "cam1"


def test_no_flag_when_face_matches_known_employee(monkeypatch):
    session = get_session()
    employee = repository.add_employee(session, "Alice")
    repository.add_face_embedding(session, employee.id, np.array([1.0, 0.0, 0.0], dtype=np.float32))
    session.close()

    analyzer = _make_analyzer(monkeypatch, [_fake_face([0.99, 0.01, 0.0])], match_threshold=0.8)

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert flags == []


def test_multiple_unknown_faces_produce_multiple_flags(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, [
        _fake_face([1.0, 0.0, 0.0]),
        _fake_face([0.0, 1.0, 0.0]),
    ])

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert len(flags) == 2


def test_no_flag_when_log_unknown_disabled(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, [_fake_face([1.0, 0.0, 0.0])], log_unknown=False)

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert flags == []


def test_no_flag_when_frame_is_none(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, [_fake_face([1.0, 0.0, 0.0])])

    flags = analyzer.analyze(frame=None, detections=[], tracks=[])

    assert flags == []


def test_no_flag_when_unknown_face_flag_disabled_in_config(monkeypatch):
    import tasks.face_id as mod
    monkeypatch.setattr(mod, "get_face_recognizer", lambda model_pack: _FakeRecognizer([_fake_face([1.0, 0.0, 0.0])]))
    config = TaskConfig(type="face_id", params={}, flags=[FlagConfig(id="unknown_face", enabled=False)])
    analyzer = FaceIDAnalyzer("cam1", config)

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert flags == []


def test_no_faces_detected_returns_no_flags(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, [])

    flags = analyzer.analyze(frame="fake-frame", detections=[], tracks=[])

    assert flags == []
