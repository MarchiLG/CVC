"""
results.py

Per-model-kind result shapes. Detection/Track (types.py) remain the
DETECTION-kind shape and are untouched; every dataclass here is that
same (class_name, confidence, bbox, ...) shape extended with whatever
extra data its kind carries (rotated corners, a mask, keypoints), so
Tracker's generic `_to_track()` (vision/tracker.py) can build any of
them the same way.

ModelResult is what CameraPipeline hands each TaskAnalyzer (as
`self.model_result`) for its own model — see tasks/base.py.
"""

from dataclasses import dataclass, field

from .model_kind import ModelKind


@dataclass
class ObbDetection:
    class_name: str
    confidence: float
    corners: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    bbox: tuple[float, float, float, float]  # axis-aligned envelope of `corners`, for legacy consumers


@dataclass
class ObbTrack(ObbDetection):
    track_id: int


@dataclass
class SegmentationInstance:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    mask: object  # numpy.ndarray, binary, frame-sized


@dataclass
class SegmentationTrack(SegmentationInstance):
    track_id: int


@dataclass
class PoseInstance:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    keypoints: list[tuple[float, float, float]]  # (x, y, confidence) per joint


@dataclass
class PoseTrack(PoseInstance):
    track_id: int


@dataclass
class ClassificationResult:
    class_name: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ModelResult:
    kind: ModelKind
    detections: list = field(default_factory=list)
    tracks: list = field(default_factory=list)
    classification: ClassificationResult | None = None
