"""
model_catalog.py

Scans the models/<kind>/ folders (project root, sibling to config/) so
the web UI can offer a model picker filtered by what a task's ModelKind
actually needs. Trusts the folder convention rather than opening every
checkpoint on every scan — ModelRegistry.kind_of() remains the
authoritative check, applied once at pipeline-build time.
"""

import os

from .model_kind import ModelKind

MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


def list_models(kind: ModelKind) -> list[str]:
    """Relative paths ("models/<kind>/name.pt"), sorted. Empty list if the
    folder doesn't exist yet (a fresh clone before any model is placed)."""
    kind_dir = os.path.join(MODELS_DIR, kind.value)
    if not os.path.isdir(kind_dir):
        return []
    names = sorted(f for f in os.listdir(kind_dir) if not f.startswith("."))
    return [f"models/{kind.value}/{name}" for name in names]


def scan_all_models() -> dict[str, list[str]]:
    return {kind.value: list_models(kind) for kind in ModelKind if kind is not ModelKind.NONE}
