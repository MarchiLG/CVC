"""
inference_engine.py

A single background thread that walks (round-robin) the cameras that
have a pipeline assigned, reads the most recent frame through
CameraManager.get_frame() and runs each camera's CameraPipeline,
publishing the result into a ResultsStore.

There is deliberately no inference thread per camera: one loaded YOLO
model is shared across cameras, and running inference inside each
capture thread would degrade capture itself (see the "Threading/process
model" section of the plan). The per-camera throttle (detect_fps, via
fps_by_camera) is what makes this single thread viable for several
cameras.

run_once() performs a single pass synchronously and deterministically —
used both by the background loop and by the tests.
"""

import threading
import time

from .camera_pipeline import CameraPipeline
from .results_store import ResultsStore


class InferenceEngine:
    def __init__(
        self,
        camera_manager,
        pipelines: dict[str, CameraPipeline],
        results_store: ResultsStore,
        fps_by_camera: dict[str, float] | None = None,
        default_fps: float = 5.0,
    ):
        self.camera_manager = camera_manager
        self.pipelines = pipelines
        self.results_store = results_store
        self.fps_by_camera = fps_by_camera or {}
        self.default_fps = default_fps

        self._running = False
        self._thread = None
        self._last_run: dict[str, float] = {}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="InferenceEngine", daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _loop(self):
        while self._running:
            self.run_once()
            time.sleep(0.01)

    def run_once(self, now: float | None = None) -> list[str]:
        """Runs one round-robin pass over the cameras, honoring the
        per-camera throttle. Returns the ids processed in this pass."""
        now = time.time() if now is None else now
        processed = []

        for camera_id, pipeline in self.pipelines.items():
            fps = self.fps_by_camera.get(camera_id, self.default_fps)
            min_interval = 1.0 / max(fps, 0.001)
            last = self._last_run.get(camera_id, 0.0)
            if (now - last) < min_interval:
                continue

            frame = self.camera_manager.get_frame(camera_id)
            if frame is None:
                continue

            result = pipeline.process(frame)
            self._last_run[camera_id] = now
            if result is not None:
                self.results_store.set(camera_id, result)
            processed.append(camera_id)

        return processed
