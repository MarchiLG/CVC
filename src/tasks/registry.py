"""
registry.py

Maps the "type" field of a TaskConfig to the corresponding TaskAnalyzer
class. Concrete tasks (item counting, PPE, missing product, face
recognition, ...) register themselves here with @register.
"""

from config.schema import TaskConfig

from .base import TaskAnalyzer

_REGISTRY: dict[str, type[TaskAnalyzer]] = {}


def register(task_type: str):
    def _decorator(cls: type[TaskAnalyzer]):
        _REGISTRY[task_type] = cls
        return cls

    return _decorator


def create(task_type: str, camera_id: str, config: TaskConfig) -> TaskAnalyzer:
    cls = _REGISTRY.get(task_type)
    if cls is None:
        raise ValueError(f"Unknown task type: '{task_type}'")
    return cls(camera_id, config)


def available_types() -> list[str]:
    return list(_REGISTRY.keys())
