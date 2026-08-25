"""
registry.py

Mapeia o campo "type" de uma TaskConfig para a classe TaskAnalyzer
correspondente. Tarefas concretas (contagem de itens, EPI, produto
ausente, reconhecimento facial, ...) se registram aqui com @register
nas fases seguintes.
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
        raise ValueError(f"Tipo de tarefa desconhecido: '{task_type}'")
    return cls(camera_id, config)


def available_types() -> list[str]:
    return list(_REGISTRY.keys())
