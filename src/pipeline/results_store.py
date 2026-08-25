"""
results_store.py

Guarda o resultado mais recente (detections, tracks) de cada câmera,
seguindo o mesmo padrão de "último valor sob lock" usado em
CameraStream.most_recent_frame — permite que a GUI leia resultados sem
bloquear a thread de inferência.
"""

import threading


class ResultsStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._results: dict[str, tuple] = {}

    def set(self, camera_id: str, result: tuple) -> None:
        with self._lock:
            self._results[camera_id] = result

    def get(self, camera_id: str):
        with self._lock:
            return self._results.get(camera_id)
