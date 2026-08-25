"""
device.py

Detecção do dispositivo de inferência (CPU/CUDA) e escolha do tamanho
de modelo padrão para cada um, com override manual via app.yaml
(vision.device / vision.model_size_override).
"""

import logging

import torch

logger = logging.getLogger("cv_central.vision.device")

_DEFAULT_MODEL_BY_DEVICE = {
    "cuda": "yolov8s.pt",
    "cpu": "yolov8n.pt",
}

_DEFAULT_FACE_MODEL_BY_DEVICE = {
    "cuda": "buffalo_l",
    "cpu": "buffalo_s",
}


def resolve_device(preferred: str = "auto") -> str:
    if preferred == "cuda":
        if torch.cuda.is_available():
            return "cuda"
        logger.warning("vision.device='cuda' solicitado mas CUDA não está disponível; usando CPU.")
        return "cpu"
    if preferred == "cpu":
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"


def default_model_for_device(device: str, override: str | None = None) -> str:
    return override or _DEFAULT_MODEL_BY_DEVICE.get(device, "yolov8n.pt")


def default_face_model_for_device(device: str, override: str | None = None) -> str:
    return override or _DEFAULT_FACE_MODEL_BY_DEVICE.get(device, "buffalo_s")
