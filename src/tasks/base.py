"""
base.py

Contrato comum para analisadores de tarefa: recebem o frame e as
detecções/rastreios mais recentes de uma câmera e retornam os Flags
que devem ser emitidos, se houver.
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

    @abstractmethod
    def analyze(self, frame, detections: list[Detection], tracks: list[Track]) -> list[Flag]:
        ...

    def flag_config(self, flag_id: str) -> FlagConfig | None:
        for flag in self.config.flags:
            if flag.id == flag_id:
                return flag
        return None
