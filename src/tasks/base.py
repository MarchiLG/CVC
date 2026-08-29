"""
base.py

Common contract for task analyzers: they receive the frame and the most
recent detections/tracks of a camera and return the Flags that should
be emitted, if any.
"""

from abc import ABC, abstractmethod

from config.schema import FlagConfig, TaskConfig
from notify.flag import Flag
from vision.types import Detection, Track


class TaskAnalyzer(ABC):
    type: str

    def __init__(self, camera_id: str, config: TaskConfig):
        self.camera_id = camera_id
        self.config = config
        # Set by CameraPipeline right before each analyze() call to the
        # ModelResult (vision/results.py) of THIS task's own model — None
        # for tasks whose kind is NONE (self-managed, like face_id) or
        # while running through the legacy detect_fn/track_fn path. Tasks
        # that only need plain Detection/Track boxes (the analyze()
        # positional arguments) never need to read this.
        self.model_result = None

    @abstractmethod
    def analyze(self, frame, detections: list[Detection], tracks: list[Track]) -> list[Flag]:
        ...

    def flag_config(self, flag_id: str) -> FlagConfig | None:
        for flag in self.config.flags:
            if flag.id == flag_id:
                return flag
        return None
