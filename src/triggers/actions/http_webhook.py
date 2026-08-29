"""
http_webhook.py

The universal fallback action: POSTs the flag as JSON to any HTTP
endpoint (Home Assistant, Node-RED, a custom server, ...). No optional
dependency beyond `requests`, which every other backend here treats as
already available.

target expected in Triggers.yaml:
    url: str (required)
    timeout_seconds: float (defaults to 5.0)
"""

import requests

from notify.flag import Flag

from .registry import register


@register("http_webhook")
def execute(target: dict, flag: Flag) -> None:
    requests.post(
        target["url"],
        json={
            "camera_id": flag.camera_id,
            "task_type": flag.task_type,
            "flag_id": flag.flag_id,
            "severity": flag.severity,
            "message": flag.message,
            "timestamp": flag.timestamp,
        },
        timeout=target.get("timeout_seconds", 5.0),
    )
