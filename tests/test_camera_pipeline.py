from config.schema import TaskConfig
from notify.flag import Flag
from notify.flag_manager import FlagManager
from notify.notifiers.base import Notifier
from pipeline.camera_pipeline import CameraPipeline
from tasks import registry
from tasks.base import TaskAnalyzer
from vision.types import Detection


class RecordingNotifier(Notifier):
    name = "recording"

    def __init__(self):
        self.received = []

    def notify(self, flag):
        self.received.append(flag)


class _AlwaysFlagAnalyzer(TaskAnalyzer):
    type = "always_flag_test_task"

    def analyze(self, frame, detections, tracks):
        return [Flag(camera_id=self.camera_id, task_type=self.type, flag_id="always", notify=["recording"])]


registry.register("always_flag_test_task")(_AlwaysFlagAnalyzer)


def test_process_returns_none_for_missing_frame():
    flag_manager = FlagManager(notifiers={"recording": RecordingNotifier()})
    pipeline = CameraPipeline("cam1", [], flag_manager)

    assert pipeline.process(None) is None


def test_process_runs_detect_track_and_analyzers():
    notifier = RecordingNotifier()
    flag_manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=0)
    task_configs = [TaskConfig(type="always_flag_test_task")]
    pipeline = CameraPipeline("cam1", task_configs, flag_manager)

    detections, tracks = pipeline.process(frame="fake-frame")

    assert detections == []  # noop_detect by default
    assert tracks == []  # noop_track by default
    assert len(notifier.received) == 1
    assert notifier.received[0].flag_id == "always"


def test_process_uses_custom_detect_and_track_fns():
    flag_manager = FlagManager(notifiers={"recording": RecordingNotifier()}, cooldown_seconds=0)

    fake_detection = Detection(class_name="box", confidence=0.9, bbox=(0, 0, 10, 10))
    pipeline = CameraPipeline(
        "cam1",
        [],
        flag_manager,
        detect_fn=lambda frame: [fake_detection],
        track_fn=lambda detections: list(detections),
    )

    detections, tracks = pipeline.process(frame="fake-frame")

    assert detections == [fake_detection]
    assert tracks == [fake_detection]
