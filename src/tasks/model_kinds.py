"""
model_kinds.py

Which ModelKind each task type expects — mirrors the LINE_TYPES/
ZONE_TYPES pattern in config/calibration.py. A task type not listed
here defaults to DETECTION (today's only kind, so this keeps every
existing tasks.yaml entry working without an update).

A task can override the registry by setting TaskConfig.model_type
explicitly in tasks.yaml — see config/schema.py.
"""

from config.schema import TaskConfig
from vision.model_kind import ModelKind

TASK_MODEL_KIND: dict[str, ModelKind] = {
    "item_counting": ModelKind.DETECTION,
    "ppe_compliance": ModelKind.DETECTION,
    "missing_product": ModelKind.DETECTION,
    "face_id": ModelKind.NONE,
    "car_identification": ModelKind.DETECTION,
    "print_monitor": ModelKind.SEGMENTATION,
}


def model_kind_for(task: TaskConfig) -> ModelKind:
    if task.model_type:
        return ModelKind(task.model_type)
    return TASK_MODEL_KIND.get(task.type, ModelKind.DETECTION)
