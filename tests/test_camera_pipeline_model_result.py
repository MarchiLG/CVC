"""
Drives CameraPipeline.process() through its orchestrated multi-engine
path (engines=..., task_engine_key=...) with fake Detector/Tracker
stand-ins, checking that each analyzer receives its OWN model's
ModelResult as `self.model_result` while every analyzer still gets the
legacy (detections, tracks) positional arguments from the first
DETECTION-kind engine.
"""

from config.schema import TaskConfig
from notify.flag import Flag
from notify.flag_manager import FlagManager
from pipeline.camera_pipeline import CameraPipeline
from tasks import registry as task_registry
from tasks.base import TaskAnalyzer
from vision.model_kind import ModelKind
from vision.results import ModelResult
from vision.types import Detection, Track


class _RecordingAnalyzer(TaskAnalyzer):
    type = "recording_test_task"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.calls = []

    def analyze(self, frame, detections, tracks):
        self.calls.append((detections, tracks, self.model_result))
        return []


task_registry.register("recording_test_task")(_RecordingAnalyzer)


class _FakeDetector:
    def __init__(self, kind, detections):
        self.kind = kind
        self._detections = detections

    def infer(self, frame):
        return ModelResult(kind=self.kind, detections=list(self._detections))


class _FakeTracker:
    def __init__(self, tracks):
        self._tracks = tracks

    def update(self, detections):
        return list(self._tracks)


def test_each_analyzer_gets_its_own_model_result():
    flag_manager = FlagManager()
    detection_track = Track(class_name="car", confidence=0.9, bbox=(0, 0, 10, 10), track_id=1)
    seg_instance = "fake-segmentation-instance"

    detection_key = ("models/detection/yolov8n.pt", ModelKind.DETECTION)
    segmentation_key = ("models/segmentation/print.pt", ModelKind.SEGMENTATION)

    engines = {
        detection_key: (_FakeDetector(ModelKind.DETECTION, ["det"]), _FakeTracker([detection_track])),
        segmentation_key: (_FakeDetector(ModelKind.SEGMENTATION, [seg_instance]), _FakeTracker([seg_instance])),
    }
    task_configs = [
        TaskConfig(type="recording_test_task", model="models/detection/yolov8n.pt"),
        TaskConfig(type="recording_test_task", model="models/segmentation/print.pt", model_type="segmentation"),
    ]
    task_engine_key = {0: detection_key, 1: segmentation_key}

    pipeline = CameraPipeline(
        "cam1", task_configs, flag_manager,
        engines=engines, task_engine_key=task_engine_key,
    )

    detections, tracks = pipeline.process(frame="fake-frame")

    # Legacy positional args come from the DETECTION-kind engine, for both analyzers.
    assert detections == ["det"]
    assert tracks == [detection_track]

    detection_analyzer, segmentation_analyzer = pipeline.analyzers
    assert detection_analyzer.model_result.kind == ModelKind.DETECTION
    assert detection_analyzer.model_result.detections == ["det"]
    assert segmentation_analyzer.model_result.kind == ModelKind.SEGMENTATION
    assert segmentation_analyzer.model_result.detections == [seg_instance]


def test_task_with_no_engine_gets_none_model_result_but_legacy_args():
    flag_manager = FlagManager()
    detection_track = Track(class_name="person", confidence=0.8, bbox=(0, 0, 5, 5), track_id=1)
    detection_key = ("models/detection/yolov8n.pt", ModelKind.DETECTION)

    engines = {detection_key: (_FakeDetector(ModelKind.DETECTION, ["det"]), _FakeTracker([detection_track]))}
    task_configs = [TaskConfig(type="recording_test_task", model_type="none")]
    task_engine_key = {0: None}

    pipeline = CameraPipeline(
        "cam1", task_configs, flag_manager,
        engines=engines, task_engine_key=task_engine_key,
    )

    detections, tracks = pipeline.process(frame="fake-frame")

    assert detections == ["det"]
    assert tracks == [detection_track]
    analyzer = pipeline.analyzers[0]
    assert analyzer.model_result is None


def test_no_engines_falls_back_to_legacy_detect_fn_track_fn():
    flag_manager = FlagManager(cooldown_seconds=0)
    fake_detection = Detection(class_name="box", confidence=0.9, bbox=(0, 0, 10, 10))

    pipeline = CameraPipeline(
        "cam1", [], flag_manager,
        detect_fn=lambda frame: [fake_detection],
        track_fn=lambda detections: list(detections),
    )

    detections, tracks = pipeline.process(frame="fake-frame")

    assert detections == [fake_detection]
    assert tracks == [fake_detection]
