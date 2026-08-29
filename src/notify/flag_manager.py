"""
flag_manager.py

Receives Flags emitted by the TaskAnalyzers, applies debouncing (so the
same alert is not notified over and over on every frame) and routes
each one to the notification channels listed in flag.notify.

Listeners (add_listener) are a separate, undebounced path: they fire on
EVERY emit() call, before the notify-channel cooldown gate. This is
what triggers/engine.py's TriggerEngine hooks into — a Modbus
actuation shouldn't be silently limited to once per cooldown_seconds
just because that happens to be the desktop-notification default, and
each task's own dwell/threshold logic already gates how often a Flag is
constructed in the first place.
"""

import threading
from typing import Callable

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
        self._listeners: list[Callable[[Flag], None]] = []

    def add_listener(self, callback: Callable[[Flag], None]) -> None:
        self._listeners.append(callback)

    def emit(self, flag: Flag) -> None:
        with self._lock:
            self.history.append(flag)
            if len(self.history) > _MAX_HISTORY:
                del self.history[: len(self.history) - _MAX_HISTORY]

            key = (flag.camera_id, flag.flag_id)
            last = self._last_notified.get(key)
            debounced = last is not None and (flag.timestamp - last) < self.cooldown_seconds
            if not debounced:
                self._last_notified[key] = flag.timestamp

        for callback in self._listeners:
            callback(flag)

        if debounced:
            return

        for channel in (flag.notify or ["log"]):
            notifier = self.notifiers.get(channel)
            if notifier is not None:
                notifier.notify(flag)

    def recent(self, limit: int = 50) -> list[Flag]:
        with self._lock:
            return self.history[-limit:]
