"""
model_registry.py

Cache of loaded YOLO instances, keyed by (model path, device). Cameras
using the same model share the same instance — this avoids reloading
weights and duplicating memory per camera (see "Threading/process
model" in the architecture plan).
"""

import threading

from ultralytics import YOLO


class ModelRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._models: dict[tuple[str, str], YOLO] = {}

    def get(self, model_path: str, device: str) -> YOLO:
        key = (model_path, device)
        with self._lock:
            model = self._models.get(key)
            if model is None:
                model = YOLO(model_path)
                self._models[key] = model
            return model


default_registry = ModelRegistry()
