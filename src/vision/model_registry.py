"""
model_registry.py

Cache of loaded YOLO instances, keyed by (model path, device). Cameras
using the same model share the same instance — this avoids reloading
weights and duplicating memory per camera (see "Threading/process
model" in the architecture plan).
"""

import threading

from ultralytics import YOLO

from .model_kind import ModelKind, kind_from_ultralytics_task


class ModelRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[tuple[str, str], YOLO] = {}

    def get(self, model_path: str, device: str) -> YOLO:
        key = (model_path, device)
        with self._lock:
            model = self._models.get(key)
            if model is None:
                model = YOLO(model_path).to(device)
                self._models[key] = model
            return model

    def kind_of(self, model_path: str, device: str) -> ModelKind:
        """The ModelKind of an already-loaded (or freshly loaded) checkpoint,
        read from Ultralytics' own `model.task` attribute — the authoritative
        check that a task's configured model matches what it declares."""
        model = self.get(model_path, device)
        return kind_from_ultralytics_task(model.task)


default_registry = ModelRegistry()
