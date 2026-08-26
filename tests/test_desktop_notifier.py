from notify.flag import Flag
from notify.notifiers.desktop import DesktopNotifier


def _flag():
    return Flag(camera_id="cam1", task_type="ppe_compliance", flag_id="missing_ppe",
                severity="critical", message="Pessoa #3 sem: helmet")


def test_notify_calls_plyer_with_flag_details(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "notify.notifiers.desktop.notification.notify",
        lambda **kwargs: calls.append(kwargs),
    )

    DesktopNotifier().notify(_flag())

    assert len(calls) == 1
    assert calls[0]["message"] == "Pessoa #3 sem: helmet"
    assert "cam1" in calls[0]["title"]
    assert "CRITICAL" in calls[0]["title"]


def test_notify_swallows_backend_errors(monkeypatch):
    def _raise(**kwargs):
        raise RuntimeError("no notification backend available")

    monkeypatch.setattr("notify.notifiers.desktop.notification.notify", _raise)

    DesktopNotifier().notify(_flag())  # must not raise
