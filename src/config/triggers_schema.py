"""
triggers_schema.py

Data structures for config/Triggers.yaml — condition -> action rules
that fire on Flags (see notify/flag.py) and drive external IO. Kept
separate from schema.py because this is a sizeable, independently
evolving block, unlike the small per-task TaskConfig.
"""

from dataclasses import dataclass, field


@dataclass
class TriggerCondition:
    """Matches a Flag: a field left as None matches any value."""

    task_type: str | None = None
    flag_id: str | None = None
    camera_id: str | None = None
    severity: str | None = None


@dataclass
class TriggerAction:
    """type is a name registered in triggers/actions/registry.py
    (e.g. "mqtt", "modbus_tcp", "http_webhook"); target is whatever that
    backend needs (host/port/topic/register/... — backend-specific)."""

    type: str
    target: dict = field(default_factory=dict)


@dataclass
class TriggerRule:
    id: str
    enabled: bool = True
    condition: TriggerCondition = field(default_factory=TriggerCondition)
    actions: list[TriggerAction] = field(default_factory=list)


@dataclass
class TriggersSettings:
    mode: str = "ask"  # "ask" | "auto"
    rules: list[TriggerRule] = field(default_factory=list)
