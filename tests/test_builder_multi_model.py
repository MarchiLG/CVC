"""
Exercises pipeline/builder.py's per-(model_path, kind) engine dedupe
without loading any real YOLO weights: a fake ModelRegistry stands in
for vision.model_registry.ModelRegistry, and vision.detector.Detector
is monkeypatched so no checkpoint is ever opened.
"""

from types import SimpleNamespace

import pytest

from config.schema import AppSettings, TaskConfig, VisionSettings
from notify.flag_manager import FlagManager
from pipeline import builder
from tasks import registry as task_registry
from tasks.base import TaskAnalyzer
from vision.model_kind import ModelKind


class _NoneKindAnalyzer(TaskAnalyzer):
    """Self-managed task (like face_id), registered locally so this test
    does not depend on face_id's optional insightface/onnxruntime deps
    being installed."""

    type = "none_kind_test_task"

    def analyze(self, frame, detections, tracks):
        return []


task_registry.register("none_kind_test_task")(_NoneKindAnalyzer)


class _FakeModelRegistry:
    """kind_of() returns whatever was declared for that path, ignoring
    device — good enough to test the builder's dedupe/validation logic
    without a real checkpoint."""

    def __init__(self, kind_by_path: dict):
        self.kind_by_path = kind_by_path
        self.get_calls = []

    def get(self, model_path, device):
        self.get_calls.append((model_path, device))
        return SimpleNamespace(model_path=model_path)

    def kind_of(self, model_path, device):
        return self.kind_by_path[model_path]


@pytest.fixture(autouse=True)
def _stub_detector(monkeypatch):
    """Detector normally loads a real YOLO model in __init__ via
    ModelRegistry.get() — replace it with a stand-in that just records
    what it was built with, so build_camera_pipeline() never touches
    ultralytics."""

    class _StubDetector:
        def __init__(self, model_path, device, registry, kind=ModelKind.DETECTION, confidence=0.4):
            self.model_path = model_path
            self.device = device
            self.kind = kind
            registry.get(model_path, device)

    monkeypatch.setattr(builder, "Detector", _StubDetector)


def _settings():
    # Pin device=cpu: on a machine with CUDA available, "auto" would
    # resolve to the cuda default model path and break the fixed
    # model paths these tests assert against.
    return AppSettings(vision=VisionSettings(device="cpu"))


def test_tasks_with_no_explicit_model_share_one_engine():
    registry = _FakeModelRegistry({"models/detection/yolov8n.pt": ModelKind.DETECTION})
    tasks = [
        TaskConfig(type="item_counting", params={"counting_line": {"p1": [0, 0], "p2": [1, 1]}}),
        TaskConfig(type="missing_product", params={"zones": [{"name": "z", "polygon": [[0, 0], [1, 0], [1, 1]], "expected_class": "box"}]}),
    ]

    pipeline = builder.build_camera_pipeline("cam1", tasks, FlagManager(), _settings(), registry)

    assert len(pipeline.engines) == 1
    key = next(iter(pipeline.engines))
    assert pipeline.task_engine_key[0] == key
    assert pipeline.task_engine_key[1] == key


def test_tasks_with_different_explicit_models_get_independent_engines():
    registry = _FakeModelRegistry({
        "models/detection/a.pt": ModelKind.DETECTION,
        "models/detection/b.pt": ModelKind.DETECTION,
    })
    tasks = [
        TaskConfig(type="item_counting", model="models/detection/a.pt",
                   params={"counting_line": {"p1": [0, 0], "p2": [1, 1]}}),
        TaskConfig(type="missing_product", model="models/detection/b.pt",
                   params={"zones": [{"name": "z", "polygon": [[0, 0], [1, 0], [1, 1]], "expected_class": "box"}]}),
    ]

    pipeline = builder.build_camera_pipeline("cam1", tasks, FlagManager(), _settings(), registry)

    assert len(pipeline.engines) == 2
    assert pipeline.task_engine_key[0] != pipeline.task_engine_key[1]


def test_kind_mismatch_raises_and_is_swallowed_by_build_pipelines(caplog):
    registry = _FakeModelRegistry({"models/segmentation/seg.pt": ModelKind.SEGMENTATION})
    tasks_by_camera = {
        "cam1": [TaskConfig(type="item_counting", model="models/segmentation/seg.pt",
                             params={"counting_line": {"p1": [0, 0], "p2": [1, 1]}})],
    }

    pipelines, fps = builder.build_pipelines(["cam1"], tasks_by_camera, FlagManager(), _settings(), registry)

    assert pipelines == {}


def test_task_with_none_kind_gets_no_engine():
    registry = _FakeModelRegistry({})
    tasks = [TaskConfig(type="none_kind_test_task", model_type="none")]

    pipeline = builder.build_camera_pipeline("cam1", tasks, FlagManager(), _settings(), registry)

    assert pipeline.engines == {}
    assert pipeline.task_engine_key[0] is None
