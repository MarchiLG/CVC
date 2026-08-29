import pytest

pytest.importorskip("paho.mqtt.publish")

from notify.flag import Flag
from triggers.actions import mqtt


def test_publishes_flag_payload_to_topic(monkeypatch):
    calls = []
    monkeypatch.setattr(mqtt.mqtt_publish, "single", lambda topic, payload, qos, hostname, port: calls.append(
        (topic, payload, qos, hostname, port)
    ))

    flag = Flag(camera_id="cam1", task_type="item_counting", flag_id="count_threshold", severity="warning")
    mqtt.execute({"host": "192.168.1.50", "topic": "cv/alerts"}, flag)

    assert len(calls) == 1
    topic, payload, qos, hostname, port = calls[0]
    assert topic == "cv/alerts"
    assert hostname == "192.168.1.50"
    assert port == 1883
    assert qos == 0
    assert '"flag_id": "count_threshold"' in payload


def test_uses_custom_port_and_qos(monkeypatch):
    calls = []
    monkeypatch.setattr(mqtt.mqtt_publish, "single", lambda topic, payload, qos, hostname, port: calls.append((qos, port)))

    mqtt.execute({"host": "h", "topic": "t", "port": 8883, "qos": 2}, Flag(camera_id="c", task_type="t", flag_id="f"))

    assert calls == [(2, 8883)]
