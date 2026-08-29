"""
schema.py

Data structures for the three configuration sources of the
application: cameras.yaml (camera registry), tasks.yaml (vision tasks
per camera) and app.yaml (global settings).
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
    """A computer vision task assigned to a camera.

    `params` is left as a free-form dict because each TaskAnalyzer (item
    counter, PPE, missing product, face recognition, ...) defines its own
    parameter format — see tasks/base.py.
    """

    type: str
    model: str | None = None
    model_type: str | None = None  # "detection"|"obb"|"segmentation"|"pose"|"classification"; overrides the
    # task-type -> kind registry in tasks/model_kinds.py when set. Left unset by every built-in task type today.
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
class UiSettings:
    """Interface language.

    English is the default. It sets the language of the desktop GUI and
    of the LLM narrator summaries, and it is the language the web
    interface starts in — there, the picker in the sidebar overrides it
    per browser (see web/static/js/i18n.js).
    """

    language: str = "en"  # "en" | "pt"


@dataclass
class AppSettings:
    vision: VisionSettings = field(default_factory=VisionSettings)
    db: DbSettings = field(default_factory=DbSettings)
    llm: LlmSettings = field(default_factory=LlmSettings)
    notify: NotifySettings = field(default_factory=NotifySettings)
    ui: UiSettings = field(default_factory=UiSettings)
