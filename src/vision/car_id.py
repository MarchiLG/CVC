"""
car_id.py

The trademark classifier and color extraction car_identification.py
runs over a cropped car region — the two secondary steps that don't
need the optional EasyOCR dependency (see vision/plate_reader.py for
the OCR one, kept separate so this module always imports cleanly):

    TrademarkClassifier  a genuine classification-kind model (Ultralytics
                         "-cls" checkpoint), reusing Detector's own
                         CLASSIFICATION parsing via ModelResult. Cached
                         by (model_path, device), same pattern as
                         ModelRegistry/get_face_recognizer.
    dominant_color()     NOT a model — k-means over the crop's HSV pixels
                         mapped to a small named palette. More robust
                         than a trained color classifier for paint under
                         varying lighting, and needs no checkpoint.
"""

import threading

import cv2
import numpy as np

from .detector import Detector
from .model_kind import ModelKind
from .model_registry import default_registry

# BGR is not useful for "what color is this car" (paint color reads best
# by hue/lightness) — classification below works in HSV, OpenCV's
# convention: H in [0,180), S and V in [0,255].
#
# Low-saturation pixels (paint that reads as black/white/silver/gray)
# are classified by brightness alone — hue is meaningless noise on a
# desaturated pixel. Saturated pixels are classified by hue distance to
# a small set of named chromatic colors, with a low-value cutoff for
# brown (an orange hue at low brightness).
_ACHROMATIC_BY_MAX_VALUE = (
    (60, "black"),
    (130, "gray"),
    (200, "silver"),
    (256, "white"),
)
_SATURATION_CUTOFF = 40
_BROWN_VALUE_CUTOFF = 90
_CHROMATIC_HUES = {
    "red": 0,
    "orange": 15,
    "yellow": 30,
    "green": 60,
    "blue": 120,
}


class TrademarkClassifier:
    def __init__(self, model_path: str, device: str):
        self._detector = Detector(
            model_path=model_path, device=device, registry=default_registry, kind=ModelKind.CLASSIFICATION,
        )

    def classify(self, crop) -> tuple[str, float]:
        """(class_name, confidence) — ("", 0.0) if the crop is empty or
        the model produced nothing usable."""
        if crop is None or crop.size == 0:
            return "", 0.0
        classification = self._detector.infer(crop).classification
        if classification is None:
            return "", 0.0
        return classification.class_name, classification.confidence


_classifier_lock = threading.Lock()
_classifier_cache: dict[tuple[str, str], TrademarkClassifier] = {}


def get_trademark_classifier(model_path: str, device: str) -> TrademarkClassifier:
    key = (model_path, device)
    with _classifier_lock:
        classifier = _classifier_cache.get(key)
        if classifier is None:
            classifier = TrademarkClassifier(model_path, device)
            _classifier_cache[key] = classifier
        return classifier


def dominant_color(crop, k: int = 3) -> str:
    """Dominant named color of `crop` ("" if the crop is empty): k-means
    over its HSV pixels, then the biggest cluster's center mapped to the
    closest entry in _NAMED_COLORS_HSV (hue treated as circular)."""
    if crop is None or crop.size == 0:
        return ""

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV).reshape(-1, 3).astype(np.float32)
    k = min(k, len(hsv))
    if k < 1:
        return ""

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _compactness, labels, centers = cv2.kmeans(hsv, k, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)

    counts = np.bincount(labels.flatten(), minlength=k)
    dominant_center = centers[int(np.argmax(counts))]
    return _closest_named_color(dominant_center)


def _closest_named_color(hsv_center) -> str:
    h, s, v = hsv_center

    if s < _SATURATION_CUTOFF:
        for max_value, name in _ACHROMATIC_BY_MAX_VALUE:
            if v < max_value:
                return name
        return "white"

    if v < _BROWN_VALUE_CUTOFF:
        return "brown"

    best_name, best_hue_diff = "", float("inf")
    for name, hue in _CHROMATIC_HUES.items():
        hue_diff = min(abs(h - hue), 180 - abs(h - hue))  # hue wraps around at 180 in OpenCV
        if hue_diff < best_hue_diff:
            best_name, best_hue_diff = name, hue_diff
    return best_name
