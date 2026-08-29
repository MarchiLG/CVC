from notify.flag import Flag
from notify.flag_manager import FlagManager
from notify.notifiers.base import Notifier


class RecordingNotifier(Notifier):
    name = "recording"

    def __init__(self):
        self.received = []

    def notify(self, flag):
        self.received.append(flag)


def _make_flag(timestamp, flag_id="missing_ppe", notify=("recording",)):
    return Flag(
        camera_id="cam1",
        task_type="ppe_compliance",
        flag_id=flag_id,
        message="test",
        notify=list(notify),
        timestamp=timestamp,
    )


def test_emit_routes_to_configured_notifier():
    notifier = RecordingNotifier()
    manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=30.0)

    manager.emit(_make_flag(timestamp=100.0))

    assert len(notifier.received) == 1
    assert notifier.received[0].flag_id == "missing_ppe"


def test_emit_debounces_within_cooldown():
    notifier = RecordingNotifier()
    manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=30.0)

    manager.emit(_make_flag(timestamp=100.0))
    manager.emit(_make_flag(timestamp=110.0))  # still within cooldown

    assert len(notifier.received) == 1
    assert len(manager.history) == 2  # still recorded in history, just not re-notified


def test_emit_notifies_again_after_cooldown():
    notifier = RecordingNotifier()
    manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=30.0)

    manager.emit(_make_flag(timestamp=100.0))
    manager.emit(_make_flag(timestamp=135.0))  # past cooldown

    assert len(notifier.received) == 2


def test_different_cameras_and_flag_ids_do_not_share_cooldown():
    notifier = RecordingNotifier()
    manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=30.0)

    manager.emit(_make_flag(timestamp=100.0, flag_id="missing_ppe"))
    manager.emit(_make_flag(timestamp=101.0, flag_id="unknown_face"))

    assert len(notifier.received) == 2


def test_recent_returns_most_recent_flags_up_to_limit():
    manager = FlagManager(notifiers={"recording": RecordingNotifier()})
    for i in range(5):
        manager.emit(_make_flag(timestamp=float(i), flag_id=f"flag{i}"))

    recent = manager.recent(limit=2)

    assert [f.flag_id for f in recent] == ["flag3", "flag4"]


def test_listener_fires_on_every_emit():
    manager = FlagManager(notifiers={"recording": RecordingNotifier()})
    seen = []
    manager.add_listener(seen.append)

    manager.emit(_make_flag(timestamp=100.0))
    manager.emit(_make_flag(timestamp=101.0))

    assert len(seen) == 2


def test_listener_fires_even_when_notify_channel_dispatch_is_debounced():
    """The key regression this proves: a trigger rule (via add_listener)
    must not be silently throttled by the SAME cooldown that limits how
    often a notify channel (log/desktop/db) re-announces the same alert —
    see flag_manager.py's module docstring."""
    notifier = RecordingNotifier()
    manager = FlagManager(notifiers={"recording": notifier}, cooldown_seconds=30.0)
    seen = []
    manager.add_listener(seen.append)

    manager.emit(_make_flag(timestamp=100.0))
    manager.emit(_make_flag(timestamp=110.0))  # within cooldown -> notifier is debounced

    assert len(notifier.received) == 1  # channel dispatch WAS debounced
    assert len(seen) == 2  # but the listener still saw both
