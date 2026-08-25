"""
streaming.py

Delivers video to the browser in two formats:

    MJPEG   (`multipart/x-mixed-replace`) for live video — every frame
            is a separate JPEG divided by a boundary on the SAME HTTP
            connection. The browser's `<img src="...">` understands this
            natively, so the UI needs no WebSocket, no WebRTC and no
            video player: it is literally an <img> tag.

    JPEG    a single frame, for the calibration screen (which needs a
            frozen frame at native resolution so the clicked
            coordinates match the pixels stored in tasks.yaml).

The detection boxes are drawn here by the same vision/overlay.py used
by the Qt GUI, so both interfaces show the same overlay.
"""

import logging
import time

import cv2
import numpy as np

from vision.overlay import draw_tracks

logger = logging.getLogger("cv_central.web.streaming")

# Separator between frames in the multipart stream. It must match the
# `boundary=` declared in the response Content-Type (see api.py).
BOUNDARY = "frame"

# Defaults for live streaming. All overridable through the query string
# (?width=&quality=&fps=) — useful to cut bandwidth when many cameras
# share the grid, or to raise quality when a camera is opened alone.
DEFAULT_MAX_WIDTH = 900
DEFAULT_QUALITY = 70      # JPEG quality, 1-100
DEFAULT_FPS = 15.0        # frames per second pushed to the browser

# Placeholder shown while the camera has not connected.
_PLACEHOLDER_SIZE = (360, 640)  # height, width
_PLACEHOLDER_BG = 18            # very dark grey (same family as the UI background)


def encode_jpeg(frame, quality: int = DEFAULT_QUALITY) -> bytes | None:
    """Encodes a BGR frame as JPEG. Returns None if encoding fails."""
    ok, buffer = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        return None
    return buffer.tobytes()


def resize_to_width(frame, max_width: int):
    """Shrinks the frame to fit `max_width`, preserving the aspect
    ratio. It never enlarges a smaller frame (that would only waste
    bandwidth)."""
    height, width = frame.shape[:2]
    if max_width <= 0 or width <= max_width:
        return frame
    scale = max_width / float(width)
    return cv2.resize(frame, (max_width, int(height * scale)), interpolation=cv2.INTER_AREA)


def placeholder_frame(text: str = "NO SIGNAL"):
    """Synthetic frame for when there is no camera image yet — it avoids
    a broken <img> in the grid while RTSP has not connected.

    The text is intentionally not translated: it is burned into the
    video pixels by OpenCV, and the stream is shared by every viewer,
    who may each have picked a different language.
    """
    height, width = _PLACEHOLDER_SIZE
    frame = np.full((height, width, 3), _PLACEHOLDER_BG, dtype=np.uint8)

    (text_w, text_h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)
    origin = ((width - text_w) // 2, (height + text_h) // 2)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, 0.7, (110, 110, 110), 1, cv2.LINE_AA)
    return frame


def render_frame(runtime, camera_id: str, *, overlay: bool = True, max_width: int = 0):
    """Most recent frame of the camera, with detections drawn.

    Returns the placeholder when the camera has not delivered any frame
    yet, so callers never have to deal with None.
    """
    frame = runtime.camera_manager.get_frame(camera_id)
    if frame is None:
        return placeholder_frame()

    if overlay:
        result = runtime.results_store.get(camera_id)
        if result is not None:
            _detections, tracks = result
            frame = draw_tracks(frame, tracks)

    return resize_to_width(frame, max_width)


def mjpeg_stream(
    runtime,
    camera_id: str,
    *,
    max_width: int = DEFAULT_MAX_WIDTH,
    quality: int = DEFAULT_QUALITY,
    fps: float = DEFAULT_FPS,
    overlay: bool = True,
):
    """Endless generator of multipart parts, one per frame.

    It runs until the browser closes the connection (Starlette then
    closes the generator and GeneratorExit ends the loop). The
    `time.sleep` at the end of each round is what caps CPU/bandwidth
    usage: without it, the loop would resend the same frame thousands of
    times per second.
    """
    interval = 1.0 / max(fps, 0.1)
    header_prefix = f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: ".encode()

    try:
        while True:
            started_at = time.monotonic()

            frame = render_frame(runtime, camera_id, overlay=overlay, max_width=max_width)
            jpeg = encode_jpeg(frame, quality)

            if jpeg is not None:
                yield header_prefix + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n"

            # Subtract the time capture/encoding already consumed, so
            # the real pace lands near the requested fps instead of
            # always below it.
            elapsed = time.monotonic() - started_at
            time.sleep(max(0.0, interval - elapsed))
    except GeneratorExit:
        logger.debug("Client disconnected from the stream of camera '%s'.", camera_id)
        raise
