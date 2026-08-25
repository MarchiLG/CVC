"""
camera_pipeline.py

Compõe, para UMA câmera, a cadeia: detector -> tracker -> analisadores
de tarefa -> FlagManager. Cada CameraPipeline é construído a partir das
TaskConfig atribuídas àquela câmera em tasks.yaml.

Por padrão, detect_fn/track_fn são passthroughs sem inferência real —
a fase 2 substitui esses parâmetros pelo Detector/Tracker de verdade
(vision/detector.py, vision/tracker.py) sem precisar alterar esta
classe.
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
