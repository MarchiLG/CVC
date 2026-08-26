"""
camera_pipeline.py

Composes, for ONE camera, the chain: detector -> tracker -> task
analyzers -> FlagManager. Each CameraPipeline is built from the
TaskConfig entries assigned to that camera in tasks.yaml.

By default, detect_fn/track_fn are passthroughs without real inference
— the builder replaces these parameters with the actual
Detector/Tracker (vision/detector.py, vision/tracker.py) without this
class having to change.
"""

from config.schema import TaskConfig
from notify.flag_manager import FlagManager
from tasks.base import TaskAnalyzer
from tasks.registry import create as create_task
from vision.types import Detection, Track


def noop_detect(frame) -> list[Detection]:
    return []


def noop_track(detections: list[Detection]) -> list[Track]:
    return []


class CameraPipeline:
    def __init__(
        self,
        camera_id: str,
        task_configs: list[TaskConfig],
        flag_manager: FlagManager,
        detect_fn=noop_detect,
        track_fn=noop_track,
    ):
        self.camera_id = camera_id
        self.flag_manager = flag_manager
        self.detect_fn = detect_fn
        self.track_fn = track_fn
        self.analyzers: list[TaskAnalyzer] = [
            create_task(cfg.type, camera_id, cfg) for cfg in task_configs
        ]

    def process(self, frame):
        if frame is None:
            return None

        detections = self.detect_fn(frame)
        tracks = self.track_fn(detections)

        for analyzer in self.analyzers:
            for flag in analyzer.analyze(frame, detections, tracks):
                self.flag_manager.emit(flag)

        return detections, tracks
