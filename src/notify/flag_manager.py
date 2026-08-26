"""
flag_manager.py

Receives Flags emitted by the TaskAnalyzers, applies debouncing (so the
same alert is not notified over and over on every frame) and routes
each one to the notification channels listed in flag.notify.
"""

import threading

from .flag import Flag
from .notifiers.base import Notifier
from .notifiers.log_notifier import LogNotifier

_MAX_HISTORY = 1000


class FlagManager:
    def __init__(self, notifiers: dict[str, Notifier] | None = None, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.notifiers: dict[str, Notifier] = notifiers or {"log": LogNotifier()}
        self._lock = threading.Lock()
        self._last_notified: dict[tuple[str, str], float] = {}
        self.history: list[Flag] = []

    def emit(self, flag: Flag) -> None:
        with self._lock:
            self.history.append(flag)
            if len(self.history) > _MAX_HISTORY:
                del self.history[: len(self.history) - _MAX_HISTORY]

            key = (flag.camera_id, flag.flag_id)
            last = self._last_notified.get(key)
            if last is not None and (flag.timestamp - last) < self.cooldown_seconds:
                return
            self._last_notified[key] = flag.timestamp

        for channel in (flag.notify or ["log"]):
            notifier = self.notifiers.get(channel)
            if notifier is not None:
                notifier.notify(flag)

    def recent(self, limit: int = 50) -> list[Flag]:
        with self._lock:
            return self.history[-limit:]
