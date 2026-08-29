"""
tracker.py

Per-camera tracker: associates Detections across frames with persistent
ids by IOU (intersection over union) + class — a simplified take on
ByteTrack/BoT-SORT style tracking (greedy IOU matching tolerating a few
unmatched frames), enough for item counting and dwell time
calculations.

It deliberately does not use ultralytics.trackers directly: those
internals expect a Results object per call and keep state inside the
YOLO model instance itself — a problem here because the model is shared
across cameras (ModelRegistry) and each camera needs independent
tracking state. This tracker is purely algorithmic (no neural network),
so instantiating one per camera is cheap — see "Threading/process
model" in the architecture plan.
"""

from dataclasses import dataclass

from .types import Detection, Track


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_w = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    inter_h = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter_area = inter_w * inter_h
    if inter_area <= 0:
        return 0.0

    a_area = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    b_area = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = a_area + b_area - inter_area
    return inter_area / union if union > 0 else 0.0


@dataclass
class _TrackState:
    track_id: int
    detection: Detection
    misses: int = 0


class Tracker:
    """Greedy IOU tracker holding its own state — one instance per camera.

    `track_cls` defaults to Track (today's only kind); pass one of the
    other *Track dataclasses (vision/results.py) to track OBB/segmentation
    /pose results instead — every one of them is its *Detection/*Instance
    counterpart plus `track_id`, which is what makes the generic
    `_to_track()` below work without per-kind branching."""

    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 5, track_cls: type = Track):
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self.track_cls = track_cls
        self._tracks: list[_TrackState] = []
        self._next_id = 1

    def update(self, detections: list) -> list:
        candidates = []
        for ti, track in enumerate(self._tracks):
            for di, det in enumerate(detections):
                if track.detection.class_name != det.class_name:
                    continue
                score = _iou(track.detection.bbox, det.bbox)
                if score >= self.iou_threshold:
                    candidates.append((score, ti, di))
        candidates.sort(key=lambda c: c[0], reverse=True)

        matched_tracks: set[int] = set()
        matched_dets: set[int] = set()
        matches = []
        for _score, ti, di in candidates:
            if ti in matched_tracks or di in matched_dets:
                continue
            matched_tracks.add(ti)
            matched_dets.add(di)
            matches.append((ti, di))

        result: list = []
        for ti, di in matches:
            track = self._tracks[ti]
            track.detection = detections[di]
            track.misses = 0
            result.append(_to_track(track, self.track_cls))

        remaining_tracks = []
        for ti, track in enumerate(self._tracks):
            if ti in matched_tracks:
                remaining_tracks.append(track)
                continue
            track.misses += 1
            if track.misses <= self.max_misses:
                remaining_tracks.append(track)
        self._tracks = remaining_tracks

        for di, detection in enumerate(detections):
            if di in matched_dets:
                continue
            new_track = _TrackState(track_id=self._next_id, detection=detection)
            self._next_id += 1
            self._tracks.append(new_track)
            result.append(_to_track(new_track, self.track_cls))

        return result


def _to_track(state: _TrackState, track_cls: type):
    return track_cls(**vars(state.detection), track_id=state.track_id)
