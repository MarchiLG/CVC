"""
missing_product.py

Para cada zona configurada com uma classe esperada (expected_class),
verifica se existe alguma detecção dessa classe com o centro dentro da
zona. Se a zona ficar vazia por mais de absence_dwell_seconds
seguidos, emite o Flag "missing_product". Usa "detections" (não
"tracks") pois presença/ausência num slot não depende de rastrear um
id específico entre frames.

params esperados em tasks.yaml:
    zones: [{name: str, polygon: [[x,y], ...], expected_class: str}]
    absence_dwell_seconds: float (default 10)
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
                message=f"Zona '{name}' sem '{expected_class}' há mais de {self.absence_seconds:.0f}s",
                notify=flag_config.notify,
            ))

        return flags
