"""
detector.py

Runs YOLO inference over a frame and converts the result into the
shape the rest of the app expects: plain Detection objects for
DETECTION-kind models (the tracker and every existing TaskAnalyzer's
positional `detections`/`tracks` arguments), or a ModelResult carrying
the richer per-kind shape (OBB corners, segmentation masks, pose
keypoints, classification scores) for the other kinds — see
vision/results.py and tasks/base.py's `self.model_result`.
"""

import cv2

from .model_kind import ModelKind
from .model_registry import ModelRegistry
from .results import (
    ClassificationResult,
    ModelResult,
    ObbDetection,
    PoseInstance,
    SegmentationInstance,
)
from .types import Detection


class Detector:
    def __init__(
        self,
        model_path: str,
        device: str,
        registry: ModelRegistry,
        confidence: float = 0.4,
        kind: ModelKind = ModelKind.DETECTION,
    ):
        self.model_path = model_path
        self.device = device
        self.confidence = confidence
        self.kind = kind
        self._model = registry.get(model_path, device)

    def detect(self, frame) -> list[Detection]:
        """Legacy DETECTION-only entry point — kept so any existing direct
        caller keeps working unchanged."""
        return self.infer(frame).detections

    def infer(self, frame) -> ModelResult:
        results = self._model.predict(frame, device=self.device, conf=self.confidence, verbose=False)
        if not results:
            return ModelResult(kind=self.kind)

        result = results[0]
        if self.kind is ModelKind.DETECTION:
            return ModelResult(kind=self.kind, detections=_parse_detect(result))
        if self.kind is ModelKind.OBB:
            return ModelResult(kind=self.kind, detections=_parse_obb(result))
        if self.kind is ModelKind.SEGMENTATION:
            return ModelResult(kind=self.kind, detections=_parse_segmentation(result))
        if self.kind is ModelKind.POSE:
            return ModelResult(kind=self.kind, detections=_parse_pose(result))
        if self.kind is ModelKind.CLASSIFICATION:
            return ModelResult(kind=self.kind, classification=_parse_classification(result))

        raise ValueError(f"Detector has no parser for kind '{self.kind}'.")


def _parse_detect(result) -> list[Detection]:
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


def _parse_obb(result) -> list[ObbDetection]:
    names = result.names
    detections = []
    obb = result.obb
    if obb is None:
        return detections
    for i in range(len(obb)):
        cls_id = int(obb.cls[i])
        confidence = float(obb.conf[i])
        corners = tuple((float(x), float(y)) for x, y in obb.xyxyxyxy[i].tolist())
        xs = [c[0] for c in corners]
        ys = [c[1] for c in corners]
        detections.append(
            ObbDetection(
                class_name=names.get(cls_id, str(cls_id)),
                confidence=confidence,
                corners=corners,
                bbox=(min(xs), min(ys), max(xs), max(ys)),
            )
        )
    return detections


def _parse_segmentation(result) -> list[SegmentationInstance]:
    names = result.names
    instances = []
    masks = result.masks
    if result.boxes is None or masks is None:
        return instances

    frame_h, frame_w = result.orig_shape
    mask_data = masks.data.cpu().numpy()
    for i, box in enumerate(result.boxes):
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
        mask = cv2.resize(mask_data[i], (frame_w, frame_h), interpolation=cv2.INTER_NEAREST)
        instances.append(
            SegmentationInstance(
                class_name=names.get(cls_id, str(cls_id)),
                confidence=confidence,
                bbox=(x1, y1, x2, y2),
                mask=mask,
            )
        )
    return instances


def _parse_pose(result) -> list[PoseInstance]:
    names = result.names
    instances = []
    keypoints = result.keypoints
    if result.boxes is None or keypoints is None:
        return instances

    kpt_data = keypoints.data.cpu().numpy()
    for i, box in enumerate(result.boxes):
        cls_id = int(box.cls[0])
        confidence = float(box.conf[0])
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
        points = [(float(x), float(y), float(c)) for x, y, c in kpt_data[i]]
        instances.append(
            PoseInstance(
                class_name=names.get(cls_id, str(cls_id)),
                confidence=confidence,
                bbox=(x1, y1, x2, y2),
                keypoints=points,
            )
        )
    return instances


def _parse_classification(result) -> ClassificationResult:
    names = result.names
    probs = result.probs
    scores = {names.get(i, str(i)): float(p) for i, p in enumerate(probs.data.tolist())}
    top1 = int(probs.top1)
    return ClassificationResult(
        class_name=names.get(top1, str(top1)),
        confidence=float(probs.top1conf),
        scores=scores,
    )
