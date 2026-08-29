"""
Unit tests for CarIdentificationAnalyzer, mirroring test_face_id.py's
style: the trademark classifier and plate reader are monkeypatched so
no real model (and no easyocr, which may not even be installed — it's
an optional dependency) is ever loaded.
"""

import numpy as np
import pytest

pytest.importorskip("easyocr")

from config.schema import FlagConfig, TaskConfig
from tasks.car_identification import CarIdentificationAnalyzer
from vision.types import Track


class _FakeClassifier:
    def __init__(self, result=("Toyota", 0.9)):
        self.result = result

    def classify(self, crop):
        return self.result


def _config(**params):
    params.setdefault("trademark_model", "models/classification/fake.pt")
    return TaskConfig(type="car_identification", params=params, flags=[
        FlagConfig(id="car_identified", enabled=True, severity="info", notify=["log"]),
    ])


def _make_analyzer(monkeypatch, classifier_result=("Toyota", 0.9), plate_text="ABC1234", **params):
    import tasks.car_identification as mod

    monkeypatch.setattr(mod, "get_trademark_classifier", lambda model_path, device: _FakeClassifier(classifier_result))
    monkeypatch.setattr(mod, "get_plate_reader", lambda languages: _FakePlateReader(plate_text))
    monkeypatch.setattr(mod, "dominant_color", lambda crop: "red")
    return CarIdentificationAnalyzer("cam1", _config(**params))


class _FakePlateReader:
    def __init__(self, text):
        self.text = text

    def read(self, crop):
        return self.text


def _frame(h=100, w=100):
    return np.zeros((h, w, 3), dtype=np.uint8)


def _car_track(track_id=1, class_name="car", confidence=0.9, bbox=(10, 10, 50, 50)):
    return Track(class_name=class_name, confidence=confidence, bbox=bbox, track_id=track_id)


def test_identifies_car_and_returns_ordered_fields(monkeypatch):
    analyzer = _make_analyzer(monkeypatch)

    flags = analyzer.analyze(_frame(), [], [_car_track()])

    assert len(flags) == 1
    flag = flags[0]
    assert flag.flag_id == "car_identified"
    assert flag.message_params["fields"] == ["Toyota", "red", "ABC1234"]
    assert flag.message_params["track_id"] == 1


def test_ignores_non_car_classes(monkeypatch):
    analyzer = _make_analyzer(monkeypatch)

    flags = analyzer.analyze(_frame(), [], [_car_track(class_name="truck")])

    assert flags == []


def test_ignores_low_confidence_detections(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, min_confidence=0.8)

    flags = analyzer.analyze(_frame(), [], [_car_track(confidence=0.5)])

    assert flags == []


def test_cooldown_skips_recently_identified_track(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, cooldown_seconds=1000.0)

    first = analyzer.analyze(_frame(), [], [_car_track(track_id=7)])
    second = analyzer.analyze(_frame(), [], [_car_track(track_id=7)])

    assert len(first) == 1
    assert second == []


def test_different_tracks_are_identified_independently(monkeypatch):
    analyzer = _make_analyzer(monkeypatch, cooldown_seconds=1000.0)

    flags = analyzer.analyze(_frame(), [], [_car_track(track_id=1), _car_track(track_id=2)])

    assert len(flags) == 2


def test_no_flag_when_car_identified_flag_disabled(monkeypatch):
    import tasks.car_identification as mod

    monkeypatch.setattr(mod, "get_trademark_classifier", lambda model_path, device: _FakeClassifier())
    monkeypatch.setattr(mod, "get_plate_reader", lambda languages: _FakePlateReader("ABC1234"))
    monkeypatch.setattr(mod, "dominant_color", lambda crop: "red")

    config = TaskConfig(type="car_identification", params={"trademark_model": "models/classification/fake.pt"},
                         flags=[FlagConfig(id="car_identified", enabled=False)])
    analyzer = CarIdentificationAnalyzer("cam1", config)

    flags = analyzer.analyze(_frame(), [], [_car_track()])

    assert flags == []


def test_missing_trademark_model_param_raises_at_construction(monkeypatch):
    import tasks.car_identification as mod

    monkeypatch.setattr(mod, "get_trademark_classifier", lambda model_path, device: _FakeClassifier())
    monkeypatch.setattr(mod, "get_plate_reader", lambda languages: _FakePlateReader(""))

    config = TaskConfig(type="car_identification", params={}, flags=[])
    with pytest.raises(KeyError):
        CarIdentificationAnalyzer("cam1", config)
