"""
camera_stream.py

Wraps the continuous capture of ONE IP camera in a dedicated thread,
always keeping the most recent frame available for reading — without
blocking the reader (a user interface, for example) while the
network/camera responds.

Nothing beyond capture happens here on purpose: the extension point for
processing (detection, recording, running your own model, etc.) is
marked with "TODO" inside _capture_loop.
"""

import threading
import time

import cv2


class CameraStream:
    """Represents a single IP camera and its capture thread."""

    def __init__(self, camera_id: str, name: str, url: str, reconnect_delay: float = 2.0):
        self.camera_id = camera_id
        self.name = name
        self.url = url
        self.reconnect_delay = reconnect_delay

        self._capture = None
        self._thread = None
        self._running = False
        self._lock = threading.Lock()

        # Equivalent to the requested "MOST_RECENT_FRAME", but per camera:
        # each CameraStream keeps its own last frame read.
        self.most_recent_frame = None  # numpy.ndarray | None
        self.is_connected = False

    # ------------------------------------------------------------------ #
    # Thread control
    # ------------------------------------------------------------------ #
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._capture_loop,
            name=f"CameraThread-{self.camera_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._capture is not None:
            self._capture.release()
            self._capture = None
        self.is_connected = False

    # ------------------------------------------------------------------ #
    # Main capture loop
    # ------------------------------------------------------------------ #
    def _capture_loop(self):
        while self._running:
            if self._capture is None or not self._capture.isOpened():
                self._connect()
                if self._capture is None or not self._capture.isOpened():
                    self.is_connected = False
                    time.sleep(self.reconnect_delay)
                    continue

            ok, frame = self._capture.read()

            if not ok:
                self.is_connected = False
                self._capture.release()
                self._capture = None
                time.sleep(self.reconnect_delay)
                continue

            self.is_connected = True
            with self._lock:
                self.most_recent_frame = frame

            # TODO: extension point.
            # Further stages (object detection, recording to disk,
            # running your own model, etc.) should be plugged in from
            # here — or by reading get_frame() from outside this thread,
            # so the capture loop never stalls.

    def _connect(self):
        self._capture = cv2.VideoCapture(self.url)

    # ------------------------------------------------------------------ #
    # External access (thread-safe)
    # ------------------------------------------------------------------ #
    def get_frame(self):
        """Returns a copy of the most recent frame, or None if there is none yet."""
        with self._lock:
            if self.most_recent_frame is None:
                return None
            return self.most_recent_frame.copy()
