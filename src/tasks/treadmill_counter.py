"""
treadmill_counter.py

Counts items crossing a configured line (counting_line), using the
track_id so the same item is not counted twice while it moves across
the frame. Optionally emits the "count_threshold" Flag when the count
within a time window falls below the expected minimum — a sign of a
possible stoppage/jam on the conveyor.

params expected in tasks.yaml:
    counting_line: {p1: [x, y], p2: [x, y]}
    direction: "positive" | "negative" | "any"  (which crossing side
        counts — see geometry.line_side; defaults to "any")
    target_classes: [class names]  (optional; by default counts any class)
    min_count_per_window / window_seconds  (optional; enables the
        count_threshold flag)
"""

import time

from notify.flag import Flag

from .base import TaskAnalyzer
from .geometry import bbox_center, line_side
from .registry import register

_DEFAULT_WINDOW_SECONDS = 60.0
_PRUNE_AFTER_SECONDS = 300.0


@register("item_counting")
class ItemCountingAnalyzer(TaskAnalyzer):
    type = "item_counting"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        line = config.params["counting_line"]
        self.p1 = tuple(line["p1"])
        self.p2 = tuple(line["p2"])
        self.direction = config.params.get("direction", "any")
        self.target_classes = config.params.get("target_classes")
        self.min_count_per_window = config.params.get("min_count_per_window")
        self.window_seconds = config.params.get("window_seconds", _DEFAULT_WINDOW_SECONDS)

        self.count = 0
        self._last_side: dict[int, tuple[int, float]] = {}
        self._crossing_times: list[float] = []
        self._started_at = time.time()

    def analyze(self, frame, detections, tracks):
        now = time.time()

        for track in tracks:
            if self.target_classes and track.class_name not in self.target_classes:
                continue

            side = line_side(bbox_center(track.bbox), self.p1, self.p2)
            if side == 0:
                continue

            previous_entry = self._last_side.get(track.track_id)
            previous_side = previous_entry[0] if previous_entry else None
            self._last_side[track.track_id] = (side, now)

            if previous_side is None or previous_side == side:
                continue

            crossed_positive = previous_side < 0 and side > 0
            crossed_negative = previous_side > 0 and side < 0
            if self.direction == "positive" and not crossed_positive:
                continue
            if self.direction == "negative" and not crossed_negative:
                continue

            self.count += 1
            self._crossing_times.append(now)

        self._last_side = {
            track_id: entry
            for track_id, entry in self._last_side.items()
            if (now - entry[1]) <= _PRUNE_AFTER_SECONDS
        }
        self._crossing_times = [t for t in self._crossing_times if (now - t) <= self.window_seconds]

        return self._check_threshold(now)

    def _check_threshold(self, now: float) -> list[Flag]:
        flag_config = self.flag_config("count_threshold")
        if (
            flag_config is None
            or not flag_config.enabled
            or self.min_count_per_window is None
            or (now - self._started_at) < self.window_seconds
            or len(self._crossing_times) >= self.min_count_per_window
        ):
            return []

        return [Flag(
            camera_id=self.camera_id,
            task_type=self.type,
            flag_id="count_threshold",
            severity=flag_config.severity,
            message=(
                f"Count below expected: {len(self._crossing_times)}/"
                f"{self.min_count_per_window} in the last {self.window_seconds:.0f}s "
                f"(running total: {self.count})"
            ),
            notify=flag_config.notify,
            message_key="flag.count_below_threshold",
            message_params={
                "count": len(self._crossing_times),
                "expected": self.min_count_per_window,
                "seconds": f"{self.window_seconds:.0f}",
                "total": self.count,
            },
        )]
