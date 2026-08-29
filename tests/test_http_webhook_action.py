from notify.flag import Flag
from triggers.actions import http_webhook


def test_posts_flag_payload_to_target_url(monkeypatch):
    calls = []

    def _fake_post(url, json, timeout):
        calls.append((url, json, timeout))

    monkeypatch.setattr(http_webhook.requests, "post", _fake_post)

    flag = Flag(camera_id="cam1", task_type="item_counting", flag_id="count_threshold",
                severity="warning", message="Count below expected")

    http_webhook.execute({"url": "http://example.invalid/hook"}, flag)

    assert len(calls) == 1
    url, payload, timeout = calls[0]
    assert url == "http://example.invalid/hook"
    assert payload["camera_id"] == "cam1"
    assert payload["flag_id"] == "count_threshold"
    assert payload["severity"] == "warning"
    assert timeout == 5.0


def test_uses_custom_timeout_when_given(monkeypatch):
    calls = []
    monkeypatch.setattr(http_webhook.requests, "post", lambda url, json, timeout: calls.append(timeout))

    http_webhook.execute({"url": "http://x", "timeout_seconds": 2.5}, Flag(camera_id="c", task_type="t", flag_id="f"))

    assert calls == [2.5]
