"""
recognizer.py

Wrapper sobre insightface.app.FaceAnalysis para detecção facial +
extração de embedding. Providers do onnxruntime são escolhidos em
tempo de execução (CUDA se disponível, senão CPU) — o mesmo código
roda em qualquer hardware; só a instalação do pacote (onnxruntime vs
onnxruntime-gpu) muda por máquina, ver requirements.txt.

get_face_recognizer() mantém um cache por model_pack (buffalo_l/
buffalo_s/...), já que carregar os modelos do InsightFace é custoso —
mesmo padrão de ModelRegistry usado para o YOLO.
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
        """Retorna a lista de rostos detectados (objetos insightface.Face,
        cada um com .bbox, .embedding — 512d já normalizado — e .det_score)."""
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
