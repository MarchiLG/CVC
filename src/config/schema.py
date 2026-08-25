"""
schema.py

Estruturas de dados para as três fontes de configuração da aplicação:
cameras.yaml (cadastro de câmeras), tasks.yaml (tarefas de visão por
câmera) e app.yaml (ajustes globais).
"""

from dataclasses import dataclass, field


@dataclass
class CameraConfig:
    id: str
    name: str
    url: str
    enabled: bool = True


@dataclass
class FlagConfig:
    id: str
    enabled: bool = True
    severity: str = "info"
    notify: list[str] = field(default_factory=list)


@dataclass
class TaskConfig:
    """Uma tarefa de visão computacional atribuída a uma câmera.

    `params` fica como dict livre porque cada TaskAnalyzer (contador de
    itens, EPI, produto ausente, reconhecimento facial, ...) define seu
    próprio formato de parâmetros — ver tasks/base.py.
    """

    type: str
    model: str | None = None
    detect_fps: float = 5.0
    params: dict = field(default_factory=dict)
    flags: list[FlagConfig] = field(default_factory=list)


@dataclass
class VisionSettings:
    device: str = "auto"  # "auto" | "cpu" | "cuda"
    model_size_override: str | None = None


@dataclass
class DbSettings:
    enabled: bool = False
    url: str = "sqlite:///data/app.db"


@dataclass
class LlmSettings:
    enabled: bool = False
    model: str = "llama3.2:1b"
    interval_seconds: float = 60.0
    max_flags_per_summary: int = 20


@dataclass
class NotifySettings:
    desktop_enabled: bool = True


@dataclass
class AppSettings:
    vision: VisionSettings = field(default_factory=VisionSettings)
    db: DbSettings = field(default_factory=DbSettings)
    llm: LlmSettings = field(default_factory=LlmSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)
