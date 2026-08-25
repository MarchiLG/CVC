"""
loader.py

Carrega e valida cameras.yaml, tasks.yaml e app.yaml. Referências
"${VAR}" dentro dos arquivos YAML são expandidas contra variáveis de
ambiente (carregadas de um .env via python-dotenv, se presente).
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
    VisionSettings,
)

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_dotenv_loaded = False


class ConfigError(Exception):
    """Erro de configuração: arquivo malformado ou variável de ambiente ausente."""


def _ensure_dotenv_loaded():
    global _dotenv_loaded
    if not _dotenv_loaded:
        load_dotenv()
        _dotenv_loaded = True


def expand_env(value):
    """Expande "${VAR}" recursivamente em strings, listas e dicts."""
    _ensure_dotenv_loaded()

    if isinstance(value, str):
        def _replace(match):
            var_name = match.group(1)
            resolved = os.environ.get(var_name)
            if resolved is None:
                raise ConfigError(
                    f"Variável de ambiente '{var_name}' não definida "
                    f"(referenciada como '${{{var_name}}}' na configuração)."
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
            raise ConfigError(f"Câmera com campo obrigatório ausente: {exc} em {entry!r}") from exc
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
    """Retorna { camera_id: [TaskConfig, ...] }. Arquivo ausente -> dict vazio."""
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
                    detect_fps=task_entry.get("detect_fps", 5.0),
                    params=task_entry.get("params", {}),
                    flags=[_load_flag(f) for f in task_entry.get("flags", [])],
                )
            )
        result[camera_id] = tasks
    return result


def load_app_config(path: str) -> AppSettings:
    """Retorna AppSettings. Arquivo ausente -> valores padrão."""
    if not os.path.exists(path):
        return AppSettings()

    raw = _load_yaml(path)
    vision_raw = raw.get("vision", {})
    db_raw = raw.get("db", {})
    llm_raw = raw.get("llm", {})
    notify_raw = raw.get("notify", {}).get("desktop", {})

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
    )
