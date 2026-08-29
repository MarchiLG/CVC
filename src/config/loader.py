"""
loader.py

Loads and validates cameras.yaml, tasks.yaml and app.yaml. "${VAR}"
references inside the YAML files are expanded against environment
variables (loaded from a .env through python-dotenv, if present).
"""

import os
import re

import yaml
from dotenv import load_dotenv

from .schema import (
    AppSettings,
    CameraConfig,
    DbSettings,
    FlagConfig,
    LlmSettings,
    NotifySettings,
    TaskConfig,
    UiSettings,
    VisionSettings,
)
from .triggers_schema import TriggerAction, TriggerCondition, TriggerRule, TriggersSettings

SUPPORTED_LANGUAGES = ("en", "pt")

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_dotenv_loaded = False


class ConfigError(Exception):
    """Configuration error: malformed file or missing environment variable."""


def _ensure_dotenv_loaded():
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def expand_env(value):
    """Expands "${VAR}" recursively in strings, lists and dicts."""
    _ensure_dotenv_loaded()

    if isinstance(value, str):
        def _replace(match):
            var_name = match.group(1)
            resolved = os.environ.get(var_name)
            if resolved is None:
                raise ConfigError(
                    f"Environment variable '{var_name}' is not defined "
                    f"(referenced as '${{{var_name}}}' in the configuration)."
                )
            return resolved

        return _ENV_VAR_PATTERN.sub(_replace, value)

    if isinstance(value, list):
        return [expand_env(item) for item in value]

    if isinstance(value, dict):
        return {key: expand_env(item) for key, item in value.items()}

    return value


def _load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_cameras_config(path: str) -> list[CameraConfig]:
    raw = _load_yaml(path)
    cameras = []
    for entry in raw.get("cameras", []):
        try:
            cameras.append(
                CameraConfig(
                    id=entry["id"],
                    name=entry.get("name", entry["id"]),
                    url=expand_env(entry["url"]),
                    enabled=entry.get("enabled", True),
                )
            )
        except KeyError as exc:
            raise ConfigError(f"Camera missing a required field: {exc} in {entry!r}") from exc
    return cameras


def _load_flag(entry) -> FlagConfig:
    if isinstance(entry, str):
        return FlagConfig(id=entry)
    return FlagConfig(
        id=entry["id"],
        enabled=entry.get("enabled", True),
        severity=entry.get("severity", "info"),
        notify=entry.get("notify", []),
    )


def load_tasks_config(path: str) -> dict[str, list[TaskConfig]]:
    """Returns { camera_id: [TaskConfig, ...] }. Missing file -> empty dict."""
    if not os.path.exists(path):
        return {}

    raw = _load_yaml(path)
    result = {}
    for camera_id, camera_entry in (raw.get("cameras") or {}).items():
        tasks = []
        for task_entry in camera_entry.get("tasks", []):
            tasks.append(
                TaskConfig(
                    type=task_entry["type"],
                    model=task_entry.get("model"),
                    model_type=task_entry.get("model_type"),
                    detect_fps=task_entry.get("detect_fps", 5.0),
                    params=task_entry.get("params", {}),
                    flags=[_load_flag(f) for f in task_entry.get("flags", [])],
                )
            )
        result[camera_id] = tasks
    return result


def load_app_config(path: str) -> AppSettings:
    """Returns AppSettings. Missing file -> default values."""
    if not os.path.exists(path):
        return AppSettings()

    raw = _load_yaml(path)
    vision_raw = raw.get("vision", {})
    db_raw = raw.get("db", {})
    llm_raw = raw.get("llm", {})
    notify_raw = raw.get("notify", {}).get("desktop", {})
    ui_raw = raw.get("ui", {})

    return AppSettings(
        vision=VisionSettings(
            device=vision_raw.get("device", "auto"),
            model_size_override=vision_raw.get("model_size_override"),
        ),
        db=DbSettings(
            enabled=db_raw.get("enabled", False),
            url=db_raw.get("url", "sqlite:///data/app.db"),
        ),
        llm=LlmSettings(
            enabled=llm_raw.get("enabled", False),
            model=llm_raw.get("model", "llama3.2:1b"),
            interval_seconds=llm_raw.get("interval_seconds", 60.0),
            max_flags_per_summary=llm_raw.get("max_flags_per_summary", 20),
        ),
        notify=NotifySettings(
            desktop_enabled=notify_raw.get("enabled", True),
        ),
        ui=UiSettings(
            language=_normalize_language(ui_raw.get("language", "en")),
        ),
    )


def _load_trigger_condition(entry: dict) -> TriggerCondition:
    return TriggerCondition(
        task_type=entry.get("task_type"),
        flag_id=entry.get("flag_id"),
        camera_id=entry.get("camera_id"),
        severity=entry.get("severity"),
    )


def _load_trigger_action(entry: dict) -> TriggerAction:
    return TriggerAction(type=entry["type"], target=entry.get("target", {}))


def _load_trigger_rule(entry: dict) -> TriggerRule:
    return TriggerRule(
        id=entry["id"],
        enabled=entry.get("enabled", True),
        condition=_load_trigger_condition(entry.get("condition", {}) or {}),
        actions=[_load_trigger_action(a) for a in entry.get("actions", [])],
    )


def load_triggers_config(path: str) -> TriggersSettings:
    """Returns TriggersSettings. Missing file -> defaults (mode "ask",
    no rules) — same convention as load_tasks_config/load_app_config."""
    if not os.path.exists(path):
        return TriggersSettings()

    raw = _load_yaml(path)
    return TriggersSettings(
        mode=raw.get("mode", "ask"),
        rules=[_load_trigger_rule(entry) for entry in raw.get("rules", [])],
    )


def _normalize_language(value) -> str:
    """Falls back to English on anything unrecognized, so a typo in
    app.yaml degrades into the default instead of breaking startup."""
    language = str(value or "").strip().lower()
    return language if language in SUPPORTED_LANGUAGES else "en"
