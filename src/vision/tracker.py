"""
tracker.py

Tracker por câmera: associa Detections entre frames a ids persistentes
por IOU (interseção sobre união) + classe — uma versão simplificada de
tracker estilo ByteTrack/BoT-SORT (greedy IOU matching com tolerância a
alguns frames sem casar), o suficiente para contagem de itens e cálculo
de tempo de permanência (dwell time).

De propósito não usa ultralytics.trackers diretamente: aqueles internos
esperam um objeto Results por chamada e mantêm estado dentro da própria
instância do modelo YOLO — problemático aqui porque o modelo é
compartilhado entre câmeras (ModelRegistry) e cada câmera precisa de
estado de rastreio independente. Este tracker é puramente algorítmico
(sem rede neural), então instanciar um por câmera é barato — ver
"Threading/process model" no plano de arquitetura.
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
    """Tracker IOU greedy com estado próprio — uma instância por câmera."""

    def __init__(self, iou_threshold: float = 0.3, max_misses: int = 5):
        self.iou_threshold = iou_threshold
        self.max_misses = max_misses
        self._tracks: list[_TrackState] = []
        self._next_id = 1

    def update(self, detections: list[Detection]) -> list[Track]:
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

        result: list[Track] = []
        for ti, di in matches:
            track = self._tracks[ti]
            track.detection = detections[di]
            track.misses = 0
            result.append(_to_track(track))

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
            result.append(_to_track(new_track))

        return result


def _to_track(state: _TrackState) -> Track:
    return Track(
        class_name=state.detection.class_name,
        confidence=state.detection.confidence,
        bbox=state.detection.bbox,
        track_id=state.track_id,
    )
