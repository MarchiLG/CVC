"""
Smoke test exercising the real YOLO detector + tracker through the
pipeline builder and inference engine. Skipped automatically if torch/
ultralytics aren't installed, so the rest of the suite stays runnable
without the heavy ML dependencies.
"""

import time

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("ultralytics")

from config.schema import AppSettings, TaskConfig
from notify.flag_manager import FlagManager
from pipeline.builder import build_pipelines
from pipeline.inference_engine import InferenceEngine
from pipeline.results_store import ResultsStore
from vision.model_registry import ModelRegistry

# Importar o pacote "tasks" registra os TaskAnalyzers reais (fase 3) —
# the real item_counting is used below, no longer a stand-in.
import tasks  # noqa: F401,E402


class _StubCameraManager:
    def __init__(self, frame):
        self.frame = frame

    def get_frame(self, camera_id):
        return self.frame


def test_real_yolo_detector_and_tracker_produce_results():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    camera_manager = _StubCameraManager(frame)
    flag_manager = FlagManager()
    app_settings = AppSettings()  # device: auto, no override -> yolov8n on CPU
    registry = ModelRegistry()

    tasks_by_camera = {
        "cam1": [TaskConfig(
            type="item_counting",
            detect_fps=5.0,
            params={"counting_line": {"p1": [320, 0], "p2": [320, 480]}},
        )],
    }
    pipelines, fps_by_camera = build_pipelines(
        ["cam1"], tasks_by_camera, flag_manager, app_settings, registry
    )
    assert "cam1" in pipelines

    engine = InferenceEngine(camera_manager, pipelines, ResultsStore(), fps_by_camera)

    start = time.time()
    processed = engine.run_once(now=start)
    elapsed = time.time() - start

    assert processed == ["cam1"]
    result = engine.results_store.get("cam1")
    assert result is not None

    detections, tracks = result
    assert isinstance(detections, list)
    assert isinstance(tracks, list)
    assert elapsed < 15.0  # sanity bound (first call also loads the model)
