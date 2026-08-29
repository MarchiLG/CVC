"""
mqtt.py

Publishes the flag as a JSON payload to an MQTT topic — one of the two
most standard ways to reach an ESP32 (the other is Modbus TCP, see
modbus_tcp.py). Optional dependency (paho-mqtt) — this module fails to
import without it, which is exactly what makes it disappear from
available_types() (see triggers/actions/__init__.py's guard).

target expected in Triggers.yaml:
    host: str (required)
    port: int (defaults to 1883)
    topic: str (required)
    qos: int (defaults to 0)
"""

import json

import paho.mqtt.publish as mqtt_publish

from notify.flag import Flag

from .registry import register


@register("mqtt")
def execute(target: dict, flag: Flag) -> None:
    payload = json.dumps({
        "camera_id": flag.camera_id,
        "task_type": flag.task_type,
        "flag_id": flag.flag_id,
        "severity": flag.severity,
        "message": flag.message,
        "timestamp": flag.timestamp,
    })
    mqtt_publish.single(
        target["topic"],
        payload=payload,
        qos=target.get("qos", 0),
        hostname=target["host"],
        port=target.get("port", 1883),
    )
