"""
model_kind.py

The kind of model a task expects, matching the Ultralytics task types
(detect/obb/segment/pose/classify) plus NONE for tasks that manage
their own inference entirely outside the per-camera orchestrated model
set (face_id's InsightFace call is the existing precedent).

Used to: pick which models/<kind>/ folder the web UI offers for a task,
validate a configured checkpoint actually matches what a task declares
(ModelRegistry.kind_of), and choose which Detector result parser to run.
"""

from enum import Enum


class ModelKind(str, Enum):
    DETECTION = "detection"
    OBB = "obb"
    SEGMENTATION = "segmentation"
    POSE = "pose"
    CLASSIFICATION = "classification"
    NONE = "none"


# Ultralytics' own `model.task` string (set on a YOLO instance after
# loading a checkpoint) mapped to the ModelKind it corresponds to.
ULTRALYTICS_TASK_TO_KIND = {
    "detect": ModelKind.DETECTION,
    "obb": ModelKind.OBB,
    "segment": ModelKind.SEGMENTATION,
    "pose": ModelKind.POSE,
    "classify": ModelKind.CLASSIFICATION,
}


def kind_from_ultralytics_task(task: str) -> ModelKind:
    kind = ULTRALYTICS_TASK_TO_KIND.get(task)
    if kind is None:
        raise ValueError(f"Unrecognized Ultralytics model task '{task}'.")
    return kind
