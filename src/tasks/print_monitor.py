"""
print_monitor.py

Segmentation-based print-failure heuristic ("spaghetti detection"):
masks the current print on the build plate every frame, tracks the
mask's area and a shape-irregularity metric over a rolling window, and
flags an abrupt deviation as a possible failed print.

This is the MVP scope: no STL/3MF comparison. Doing that properly would
need a one-time manual camera-calibration step (a homography from the
build plate to camera pixels) that this application has no existing
concept of — config/calibration.py's LINE_TYPES/ZONE_TYPES are 2D task
geometry, unrelated to projecting a 3D mesh into the camera view — plus
a mesh-loading dependency (e.g. trimesh) to rasterize the STL's
cross-section at each print-height layer. Left as a documented future
phase; this task only ever looks at the LIVE segmentation mask.

params expected in tasks.yaml:
    print_class: str (defaults to "print")            # segmentation model's class name for the print mass
    window_size: int (defaults to 30)                   # rolling history length, in analyzed frames
    area_growth_threshold: float (defaults to 1.6)      # current/rolling-median area ratio that triggers a flag
    shape_irregularity_threshold: float (defaults to 0.35)
    min_history_before_flagging: int (defaults to 10)   # warm-up frames before the heuristic is trusted
"""

import collections
import statistics

import cv2
import numpy as np

from notify.flag import Flag

from .base import TaskAnalyzer
from .registry import register

_DEFAULT_PRINT_CLASS = "print"
_DEFAULT_WINDOW_SIZE = 30
_DEFAULT_AREA_GROWTH_THRESHOLD = 1.6
_DEFAULT_SHAPE_IRREGULARITY_THRESHOLD = 0.35
_DEFAULT_MIN_HISTORY = 10


def _mask_area(mask) -> float:
    return float(np.count_nonzero(mask))


def _shape_irregularity(mask) -> float:
    """0 for a single perfectly round/compact blob, approaching 1 as the
    mask gets more jagged OR more fragmented into separate pieces — 1 -
    isoperimetric ratio (4*pi*area / perimeter^2) computed over EVERY
    contour's area/perimeter summed together (not just the largest),
    so scattered debris/support material reads as irregular too, not
    just a single spiky blob. 0 (treated as perfectly regular) when the
    mask is empty or has no measurable perimeter."""
    mask_u8 = (mask > 0).astype(np.uint8)
    contours, _hierarchy = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return 0.0

    total_area = sum(cv2.contourArea(c) for c in contours)
    total_perimeter = sum(cv2.arcLength(c, closed=True) for c in contours)
    if total_area <= 0 or total_perimeter <= 0:
        return 0.0

    isoperimetric_ratio = (4 * np.pi * total_area) / (total_perimeter ** 2)
    return float(max(0.0, 1.0 - min(1.0, isoperimetric_ratio)))


@register("print_monitor")
class PrintMonitorAnalyzer(TaskAnalyzer):
    type = "print_monitor"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.print_class = config.params.get("print_class", _DEFAULT_PRINT_CLASS)
        self.window_size = config.params.get("window_size", _DEFAULT_WINDOW_SIZE)
        self.area_growth_threshold = config.params.get("area_growth_threshold", _DEFAULT_AREA_GROWTH_THRESHOLD)
        self.shape_irregularity_threshold = config.params.get(
            "shape_irregularity_threshold", _DEFAULT_SHAPE_IRREGULARITY_THRESHOLD,
        )
        self.min_history = config.params.get("min_history_before_flagging", _DEFAULT_MIN_HISTORY)
        self._area_history: collections.deque = collections.deque(maxlen=self.window_size)

    def analyze(self, frame, detections, tracks):
        if self.model_result is None:
            return []

        instances = [m for m in self.model_result.detections if m.class_name == self.print_class]
        if not instances:
            return []

        mask = max(instances, key=lambda m: _mask_area(m.mask)).mask
        area = _mask_area(mask)
        irregularity = _shape_irregularity(mask)

        flags: list[Flag] = []
        if len(self._area_history) >= self.min_history:
            median_area = statistics.median(self._area_history)
            area_ratio = area / median_area if median_area > 0 else 1.0

            if area_ratio >= self.area_growth_threshold or irregularity >= self.shape_irregularity_threshold:
                flag_config = self.flag_config("possible_failed_print")
                if flag_config is not None and flag_config.enabled:
                    flags.append(Flag(
                        camera_id=self.camera_id,
                        task_type=self.type,
                        flag_id="possible_failed_print",
                        severity=flag_config.severity,
                        notify=flag_config.notify,
                        message=f"Possible failed print: area x{area_ratio:.2f}, irregularity {irregularity:.2f}",
                        message_key="flag.possible_failed_print",
                        message_params={"area_ratio": f"{area_ratio:.2f}", "irregularity": f"{irregularity:.2f}"},
                    ))

        self._area_history.append(area)
        return flags
