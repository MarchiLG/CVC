"""
registry.py

Maps a TriggerAction's "type" (e.g. "mqtt", "modbus_tcp",
"http_webhook") to the function that executes it. Concrete backends
register themselves with @register — same decorator-registry shape as
tasks/registry.py, so adding a new IO protocol later (EtherNet/IP,
OPC-UA, ...) is a new file + one import line, no changes here.
"""

import logging
from typing import Callable

from notify.flag import Flag

logger = logging.getLogger("cv_central.triggers.actions")

_REGISTRY: dict[str, Callable[[dict, Flag], None]] = {}


def register(action_type: str):
    def _decorator(fn: Callable[[dict, Flag], None]):
        _REGISTRY[action_type] = fn
        return fn

    return _decorator


def execute(action_type: str, target: dict, flag: Flag) -> None:
    """Never raises — a broken action (bad host, device offline,
    misconfigured target) is logged and swallowed so it can't take the
    inference pipeline down with it."""
    fn = _REGISTRY.get(action_type)
    if fn is None:
        logger.warning("Unknown or unavailable trigger action type '%s' — skipped.", action_type)
        return
    try:
        fn(target, flag)
    except Exception:
        logger.exception("Trigger action '%s' failed.", action_type)


def available_types() -> list[str]:
    return list(_REGISTRY.keys())
