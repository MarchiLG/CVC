"""
camera_pipeline.py

Composes, for ONE camera, the chain: model engine(s) -> task analyzers
-> FlagManager. Each CameraPipeline is built from the TaskConfig
entries assigned to that camera in tasks.yaml.

Two construction modes:

  - Legacy (`detect_fn`/`track_fn`, the default): a single detect/track
    pair runs once per frame and every analyzer gets the same
    (detections, tracks) — used directly by tests and as a fallback.

  - Orchestrated (`engines`/`task_engine_key`, built by pipeline/builder.py
    for real cameras): one Detector+Tracker pair per distinct
    (model_path, ModelKind) a camera's tasks actually need. Every engine
    runs once per frame; each analyzer additionally receives its OWN
    model's ModelResult as `self.model_result` (vision/results.py),
    without changing analyze()'s positional (frame, detections, tracks)
    contract — see tasks/base.py.
"""

from config.schema import TaskConfig
from notify.flag_manager import FlagManager
from tasks.base import TaskAnalyzer
from tasks.registry import create as create_task
from vision.model_kind import ModelKind
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
        engines: dict | None = None,
        task_engine_key: dict | None = None,
    ):
        self.camera_id = camera_id
        self.flag_manager = flag_manager
        self.detect_fn = detect_fn
        self.track_fn = track_fn
        self.engines = engines or {}
        self.task_engine_key = task_engine_key or {}
        self.analyzers: list[TaskAnalyzer] = [
            create_task(cfg.type, camera_id, cfg) for cfg in task_configs
        ]

    def process(self, frame):
        if frame is None:
            return None

        if not self.engines:
            detections = self.detect_fn(frame)
            tracks = self.track_fn(detections)
            primary_detections, primary_tracks = detections, tracks
            results_by_key = {}
        else:
            results_by_key = {}
            for key, (detector, tracker) in self.engines.items():
                model_result = detector.infer(frame)
                if model_result.kind != ModelKind.CLASSIFICATION:
                    model_result.tracks = tracker.update(model_result.detections)
                results_by_key[key] = model_result
            primary_detections, primary_tracks = self._primary_detection_result(results_by_key)

        for index, analyzer in enumerate(self.analyzers):
            analyzer.model_result = results_by_key.get(self.task_engine_key.get(index)) if self.engines else None
            for flag in analyzer.analyze(frame, primary_detections, primary_tracks):
                self.flag_manager.emit(flag)

        return primary_detections, primary_tracks

    def _primary_detection_result(self, results_by_key: dict):
        """The (detections, tracks) fed positionally to every analyze()
        call, for backward compatibility with tasks that only read those
        arguments: the first DETECTION-kind engine's result, mirroring the
        pre-Phase-1 "first task's model wins" rule. Empty lists if no task
        on this camera resolves to a DETECTION-kind engine."""
        for key, model_result in results_by_key.items():
            _model_path, kind = key
            if kind is ModelKind.DETECTION:
                return model_result.detections, model_result.tracks
        return [], []
