"""
results_store.py

Holds the most recent result (detections, tracks) of each camera,
following the same "last value under a lock" pattern used in
CameraStream.most_recent_frame — this lets the interfaces read results
without blocking the inference thread.
"""

import threading


class ResultsStore:
    def __init__(self):
        self._lock = threading.Lock()
        self._results: dict[str, tuple] = {}

    def set(self, camera_id: str, result: tuple) -> None:
        with self._lock:
            self._results[camera_id] = result

    def get(self, camera_id: str):
        with self._lock:
            return self._results.get(camera_id)

    def retain(self, camera_ids) -> None:
        """Drops the result of every camera outside `camera_ids`.

        Used when reloading the pipelines (bootstrap.AppRuntime.reload_tasks):
        a camera that lost its last task no longer produces any result,
        but its last one would stay here — and both UIs would keep
        drawing boxes from a stale detection over the video, one that
        would never be refreshed again.
        """
        keep = set(camera_ids)
        with self._lock:
            for camera_id in list(self._results):
                if camera_id not in keep:
                    del self._results[camera_id]
