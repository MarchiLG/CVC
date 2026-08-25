"""
types.py

Estruturas de dados compartilhadas entre o detector, o tracker e os
TaskAnalyzers: uma Detection é uma caixa delimitadora com classe e
confiança; um Track é uma Detection com um id estável entre frames.
"""

from dataclasses import dataclass


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2


@dataclass
class Track(Detection):
    track_id: int
