"""
types.py

Data structures shared between the detector, the tracker and the
TaskAnalyzers: a Detection is a bounding box with a class and a
confidence; a Track is a Detection with an id that stays stable across
frames.
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
