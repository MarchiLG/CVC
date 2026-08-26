"""
missing_product.py

For each zone configured with an expected class (expected_class),
checks whether there is any detection of that class whose center falls
inside the zone. If the zone stays empty for longer than
absence_dwell_seconds in a row, emits the "missing_product" Flag. It
uses "detections" (not "tracks") because presence/absence in a slot
does not depend on following a specific id across frames.

params expected in tasks.yaml:
    zones: [{name: str, polygon: [[x,y], ...], expected_class: str}]
    absence_dwell_seconds: float (defaults to 10)
"""

import time

from notify.flag import Flag

from .base import TaskAnalyzer
from .geometry import bbox_center, point_in_polygon
from .registry import register

_DEFAULT_ABSENCE_SECONDS = 10.0


@register("missing_product")
class MissingProductAnalyzer(TaskAnalyzer):
    type = "missing_product"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.zones = config.params.get("zones", [])
        self.absence_seconds = config.params.get("absence_dwell_seconds", _DEFAULT_ABSENCE_SECONDS)
        self._absent_since: dict[str, float | None] = {zone["name"]: None for zone in self.zones}

    def analyze(self, frame, detections, tracks):
        now = time.time()
        flags: list[Flag] = []

        for zone in self.zones:
            name = zone["name"]
            polygon = zone["polygon"]
            expected_class = zone["expected_class"]

            present = any(
                d.class_name == expected_class and point_in_polygon(bbox_center(d.bbox), polygon)
                for d in detections
            )

            if present:
                self._absent_since[name] = None
                continue

            if self._absent_since.get(name) is None:
                self._absent_since[name] = now

            if (now - self._absent_since[name]) < self.absence_seconds:
                continue

            flag_config = self.flag_config("missing_product")
            if flag_config is None or not flag_config.enabled:
                continue

            flags.append(Flag(
                camera_id=self.camera_id,
                task_type=self.type,
                flag_id="missing_product",
                severity=flag_config.severity,
                message=(
                    f"Zone '{name}' without '{expected_class}' "
                    f"for more than {self.absence_seconds:.0f}s"
                ),
                notify=flag_config.notify,
                message_key="flag.missing_product",
                message_params={
                    "zone": name,
                    "expected_class": expected_class,
                    "seconds": f"{self.absence_seconds:.0f}",
                },
            ))

        return flags
