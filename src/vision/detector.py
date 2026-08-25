"""
detector.py

Roda a inferência YOLO sobre um frame e converte o resultado para a
lista de Detection compartilhada entre tracker e TaskAnalyzers.
"""

from .model_registry import ModelRegistry
from .types import Detection


class Detector:
    def __init__(self, model_path: str, device: str, registry: ModelRegistry, confidence: float = 0.4):
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self._model = registry.get(model_path, device)

    def detect(self, frame) -> list[Detection]:
        results = self._model.predict(frame, device=self.device, conf=self.confidence, verbose=False)
        if not results:
            return []

        result = results[0]
        names = result.names
        detections = []
        for box in result.boxes:
            cls_id = int(box.cls[0])
            confidence = float(box.conf[0])
            x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
            detections.append(
                Detection(
                    class_name=names.get(cls_id, str(cls_id)),
                    confidence=confidence,
                    bbox=(x1, y1, x2, y2),
                )
            )
        return detections
