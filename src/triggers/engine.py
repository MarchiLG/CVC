"""
engine.py

TriggerEngine evaluates every Flag against the enabled TriggerRules
(config/Triggers.yaml) and, on a match, either executes the rule's
actions right away ("auto" mode) or queues them as a PendingAction
awaiting operator approval ("ask" mode) — see web/api.py's
/api/triggers/pending routes for the approve/deny surface.

Wired in bootstrap.py via flag_manager.add_listener(trigger_engine.on_flag)
— see notify/flag_manager.py's module docstring for why a listener,
not another Notifier channel.
"""

import logging
import threading
import time
import uuid
from dataclasses import dataclass

from config.triggers_schema import TriggerAction, TriggerCondition, TriggersSettings
from notify.flag import Flag

logger = logging.getLogger("cv_central.triggers.engine")


@dataclass
class PendingAction:
    id: str
    rule_id: str
    flag: Flag
    action: TriggerAction
    created_at: float


class TriggerEngine:
    def __init__(self, settings: TriggersSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._pending: dict[str, PendingAction] = {}

    def reload(self, settings: TriggersSettings) -> None:
        self.settings = settings

    def on_flag(self, flag: Flag) -> None:
        for rule in self.settings.rules:
            if not rule.enabled or not _matches(rule.condition, flag):
                continue
            for action in rule.actions:
                self._trigger(rule.id, flag, action)

    def _trigger(self, rule_id: str, flag: Flag, action: TriggerAction) -> None:
        if self.settings.mode == "auto":
            self._execute(action, flag)
            return

        pending = PendingAction(id=uuid.uuid4().hex, rule_id=rule_id, flag=flag, action=action, created_at=time.time())
        with self._lock:
            self._pending[pending.id] = pending

    def _execute(self, action: TriggerAction, flag: Flag) -> None:
        from .actions.registry import execute as execute_action
        execute_action(action.type, action.target, flag)

    def pending(self) -> list[PendingAction]:
        with self._lock:
            return list(self._pending.values())

    def approve(self, pending_id: str) -> bool:
        with self._lock:
            pending = self._pending.pop(pending_id, None)
        if pending is None:
            return False
        self._execute(pending.action, pending.flag)
        return True

    def deny(self, pending_id: str) -> bool:
        with self._lock:
            return self._pending.pop(pending_id, None) is not None


def _matches(condition: TriggerCondition, flag: Flag) -> bool:
    return (
        (condition.task_type is None or condition.task_type == flag.task_type)
        and (condition.flag_id is None or condition.flag_id == flag.flag_id)
        and (condition.camera_id is None or condition.camera_id == flag.camera_id)
        and (condition.severity is None or condition.severity == flag.severity)
    )
