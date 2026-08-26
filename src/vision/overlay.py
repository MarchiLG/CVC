"""
overlay.py

Draws detections/tracks (and calibrated geometry: counting lines and
zones) over an OpenCV BGR frame.

It lives here, and not inside one of the interfaces, because BOTH UIs
draw exactly the same overlay: the PySide6 GUI
(gui_qt/widgets/camera_tile.py) and the MJPEG stream of the web UI
(web/streaming.py). Changing how the boxes look in one place therefore
changes both.

Color convention: OpenCV works in BGR, so every constant below is in
BGR (not RGB/hex like in CSS).
"""

import colorsys
import zlib

import cv2

# Default box color (BGR) — green, same as the original Qt GUI.
BOX_COLOR = (0, 255, 0)

# Calibrated geometry drawn on top of the video.
LINE_COLOR = (80, 200, 255)   # amber, for the counting line
ZONE_COLOR = (255, 170, 70)   # light blue, for zone polygons

_FONT = cv2.FONT_HERSHEY_SIMPLEX


def color_for_class(class_name: str) -> tuple[int, int, int]:
    """Stable color (BGR) per class name.

    Derives the hue from a checksum of the name, so "person" always gets
    the same color — across runs, across cameras and across both
    interfaces — without needing a fixed class table (the YOLO model may
    have any vocabulary, including one trained for PPE).

    Uses crc32 and NOT the built-in hash(): Python string hashing is
    randomly salted per process (PYTHONHASHSEED), which would give a
    different color on every run and different colors between the Qt GUI
    and the web server, which are separate processes.
    """
    hue = (zlib.crc32(class_name.encode("utf-8")) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.65, 1.0)
    return (int(b * 255), int(g * 255), int(r * 255))


def draw_tracks(frame, tracks, *, colored_by_class: bool = True, thickness: int = 2):
    """Draws one box + label per track. Returns a COPY of the frame
    (it never draws over the buffer the capture thread is still using).

    `tracks` are objects with .bbox, .class_name, .confidence and
    .track_id — see vision/types.py.
    """
    if not tracks:
        return frame

    frame = frame.copy()
    for track in tracks:
        color = color_for_class(track.class_name) if colored_by_class else BOX_COLOR
        x1, y1, x2, y2 = (int(v) for v in track.bbox)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, thickness)

        label = f"{track.class_name} #{track.track_id} {track.confidence:.2f}"
        _draw_label(frame, label, x1, y1, color)

    return frame


def _draw_label(frame, text: str, x: int, y: int, color, scale: float = 0.5):
    """Label with a solid background — readable over any scene, unlike
    plain text which disappears on light backgrounds."""
    (text_w, text_h), baseline = cv2.getTextSize(text, _FONT, scale, 1)
    top = max(0, y - text_h - baseline - 4)

    cv2.rectangle(frame, (x, top), (x + text_w + 6, top + text_h + baseline + 4), color, -1)
    cv2.putText(
        frame, text, (x + 3, top + text_h + 2),
        _FONT, scale, (20, 20, 20), 1, cv2.LINE_AA,
    )


def draw_task_geometry(frame, task_params: list[dict]):
    """Draws the geometry already calibrated in tasks.yaml (counting
    line and/or zone polygons) on top of the frame.

    Takes a list of task `params` dicts (the "params" field of each task
    in tasks.yaml). Unknown keys are ignored, so tasks without geometry
    (face_id, for example) simply draw nothing.
    """
    if not task_params:
        return frame

    frame = frame.copy()
    for params in task_params:
        line = (params or {}).get("counting_line")
        if line:
            _draw_counting_line(frame, line)

        for zone in (params or {}).get("zones", []) or []:
            _draw_zone(frame, zone)

    return frame


def _draw_counting_line(frame, line: dict):
    p1, p2 = line.get("p1"), line.get("p2")
    if not p1 or not p2:
        return
    cv2.line(frame, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), LINE_COLOR, 2)


def _draw_zone(frame, zone: dict):
    import numpy as np

    polygon = zone.get("polygon") or []
    if len(polygon) < 3:
        return

    points = np.array([[int(x), int(y)] for x, y in polygon], dtype=np.int32)
    cv2.polylines(frame, [points], isClosed=True, color=ZONE_COLOR, thickness=2)

    name = zone.get("name")
    if name:
        _draw_label(frame, str(name), int(points[0][0]), int(points[0][1]), ZONE_COLOR)
