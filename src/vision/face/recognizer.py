"""
recognizer.py

Wrapper over insightface.app.FaceAnalysis for face detection +
embedding extraction. The onnxruntime providers are chosen at runtime
(CUDA when available, CPU otherwise) — the same code runs on any
hardware; only the installed package (onnxruntime vs onnxruntime-gpu)
changes per machine, see requirements.txt.

get_face_recognizer() keeps a cache per model_pack (buffalo_l/
buffalo_s/...), since loading the InsightFace models is expensive — the
same pattern as the ModelRegistry used for YOLO.
"""

import threading

import onnxruntime
from insightface.app import FaceAnalysis


def available_providers() -> list[str]:
    return onnxruntime.get_available_providers()


def _select_providers() -> list[str]:
    providers = available_providers()
    if "CUDAExecutionProvider" in providers:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


class FaceRecognizer:
    def __init__(self, model_pack: str = "buffalo_s", det_size: tuple[int, int] = (640, 640)):
        providers = _select_providers()
        ctx_id = 0 if "CUDAExecutionProvider" in providers else -1

        self._app = FaceAnalysis(name=model_pack, providers=providers)
        self._app.prepare(ctx_id=ctx_id, det_size=det_size)

    def analyze(self, frame):
        """Returns the list of detected faces (insightface.Face objects,
        each with .bbox, .embedding — 512d, already normalized — and
        .det_score)."""
        return self._app.get(frame)


_cache_lock = threading.Lock()
_recognizer_cache: dict[str, FaceRecognizer] = {}


def get_face_recognizer(model_pack: str) -> FaceRecognizer:
    with _cache_lock:
        recognizer = _recognizer_cache.get(model_pack)
        if recognizer is None:
            recognizer = FaceRecognizer(model_pack=model_pack)
            _recognizer_cache[model_pack] = recognizer
        return recognizer
