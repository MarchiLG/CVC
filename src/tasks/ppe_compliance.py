"""
ppe_compliance.py

Para cada pessoa detectada dentro das zonas configuradas, verifica se
os itens de EPI exigidos (required_ppe) também estão presentes
sobrepondo a caixa da pessoa. Se algum item ficar faltando por mais de
missing_ppe_dwell_seconds seguidos, emite o Flag "missing_ppe".

Requer um modelo capaz de detectar as classes de EPI configuradas
(ex.: helmet, vest) — um YOLO treinado em COCO não tem essas classes;
atribua um modelo específico via "model" em tasks.yaml para esta tarefa.

params esperados em tasks.yaml:
    required_ppe: [nomes de classe do modelo, ex.: helmet, vest]
    zones: [{name: str, polygon: [[x,y], ...]}]  (opcional; sem zonas = frame inteiro)
    missing_ppe_dwell_seconds: float (default 30)
    person_class: nome da classe "pessoa" no modelo (default "person")
"""

import time

from notify.flag import Flag

from .base import TaskAnalyzer
from .geometry import bbox_center, bbox_overlaps, point_in_polygon
from .registry import register

_DEFAULT_DWELL_SECONDS = 30.0
_PRUNE_AFTER_SECONDS = 300.0


@register("ppe_compliance")
class PPEComplianceAnalyzer(TaskAnalyzer):
    type = "ppe_compliance"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.required_ppe = config.params.get("required_ppe", [])
        self.zones = [zone["polygon"] for zone in config.params.get("zones", [])]
        self.dwell_seconds = config.params.get("missing_ppe_dwell_seconds", _DEFAULT_DWELL_SECONDS)
        self.person_class = config.params.get("person_class", "person")

        # track_id -> {"missing_since": float | None, "missing_items": set[str], "last_seen": float}
        self._state: dict[int, dict] = {}

    def analyze(self, frame, detections, tracks):
        now = time.time()
        flags: list[Flag] = []

        people = [t for t in tracks if t.class_name == self.person_class]
        others = [t for t in tracks if t.class_name != self.person_class]

        for person in people:
            if self.zones and not any(point_in_polygon(bbox_center(person.bbox), zone) for zone in self.zones):
                continue

            missing = [
                item for item in self.required_ppe
                if not any(o.class_name == item and bbox_overlaps(person.bbox, o.bbox) for o in others)
            ]

            state = self._state.setdefault(
                person.track_id, {"missing_since": None, "missing_items": set(), "last_seen": now}
            )
            state["last_seen"] = now

            if not missing:
                state["missing_since"] = None
                state["missing_items"] = set()
                continue

            if state["missing_since"] is None:
                state["missing_since"] = now
            state["missing_items"] = set(missing)

            if (now - state["missing_since"]) < self.dwell_seconds:
                continue

            flag_config = self.flag_config("missing_ppe")
            if flag_config is None or not flag_config.enabled:
                continue

            flags.append(Flag(
                camera_id=self.camera_id,
                task_type=self.type,
                flag_id="missing_ppe",
                severity=flag_config.severity,
                message=f"Pessoa #{person.track_id} sem: {', '.join(sorted(missing))}",
                notify=flag_config.notify,
            ))

        self._state = {
            track_id: state
            for track_id, state in self._state.items()
            if (now - state["last_seen"]) <= _PRUNE_AFTER_SECONDS
        }

        return flags
