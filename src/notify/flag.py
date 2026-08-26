"""
flag.py

Represents an alert event raised by an analysis task (TaskAnalyzer) —
e.g. missing PPE, count below the expected threshold, unknown face.

About the two message fields: `message` is the rendered English text and
is what goes to the logs, to the event_log table and to the LLM
narrator prompt. `message_key` + `message_params` describe the SAME
message in a translatable form, so the web interface can render it in
the language the user picked (see web/static/js/i18n.js). Interfaces
that do not translate simply show `message`.
"""

import time
from dataclasses import dataclass, field


@dataclass
class Flag:
    camera_id: str
    task_type: str
    flag_id: str
    severity: str = "info"
    message: str = ""
    notify: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)

    # Translation key and its interpolation values. Empty for flags
    # built by hand (tests, external code) — the interfaces then fall
    # back to `message`.
    message_key: str = ""
    message_params: dict = field(default_factory=dict)
