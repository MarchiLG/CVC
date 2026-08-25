from notify.flag_manager import FlagManager
from pipeline.camera_pipeline import CameraPipeline
from pipeline.inference_engine import InferenceEngine
from pipeline.results_store import ResultsStore


class FakeCameraManager:
    def __init__(self, frames):
        self.frames = frames  # { camera_id: frame_or_None }

    def get_frame(self, camera_id):
        return self.frames.get(camera_id)


def _make_pipeline(camera_id):
    return CameraPipeline(camera_id, [], FlagManager())


def test_run_once_processes_camera_with_frame_and_updates_results_store():
    camera_manager = FakeCameraManager({"cam1": "frame-1"})
    results_store = ResultsStore()
    engine = InferenceEngine(
        camera_manager,
        pipelines={"cam1": _make_pipeline("cam1")},
        results_store=results_store,
    )

    processed = engine.run_once(now=1000.0)

    assert processed == ["cam1"]
    assert results_store.get("cam1") == ([], [])


def test_run_once_skips_camera_with_no_frame_yet():
    camera_manager = FakeCameraManager({"cam1": None})
    results_store = ResultsStore()
    engine = InferenceEngine(
        camera_manager,
        pipelines={"cam1": _make_pipeline("cam1")},
        results_store=results_store,
    )

    processed = engine.run_once(now=1000.0)

    assert processed == []
    assert results_store.get("cam1") is None


def test_run_once_throttles_per_camera_fps():
    camera_manager = FakeCameraManager({"cam1": "frame-1"})
    results_store = ResultsStore()
    engine = InferenceEngine(
        camera_manager,
        pipelines={"cam1": _make_pipeline("cam1")},
        results_store=results_store,
        fps_by_camera={"cam1": 1.0},  # min interval 1s
    )

    first = engine.run_once(now=1000.0)
    second = engine.run_once(now=1000.5)  # within throttle window
    third = engine.run_once(now=1001.5)  # past throttle window

    assert first == ["cam1"]
    assert second == []
    assert third == ["cam1"]
