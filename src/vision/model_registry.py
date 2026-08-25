"""
model_registry.py

Cache de instâncias YOLO carregadas, chaveado por (caminho do modelo,
device). Câmeras diferentes que usam o mesmo modelo compartilham a
mesma instância — evita recarregar pesos e duplicar memória por
câmera (ver "Threading/process model" no plano de arquitetura).
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
