import logging

from notify.flag import Flag
from triggers.actions import registry


def _flag():
    return Flag(camera_id="cam1", task_type="item_counting", flag_id="count_threshold")


def test_register_and_execute(monkeypatch):
    calls = []
    monkeypatch.setattr(registry, "_REGISTRY", {})
    registry.register("fake_action")(lambda target, flag: calls.append((target, flag.flag_id)))

    registry.execute("fake_action", {"x": 1}, _flag())

    assert calls == [({"x": 1}, "count_threshold")]


def test_available_types_lists_registered_actions(monkeypatch):
    monkeypatch.setattr(registry, "_REGISTRY", {})
    registry.register("a")(lambda target, flag: None)
    registry.register("b")(lambda target, flag: None)

    assert set(registry.available_types()) == {"a", "b"}


def test_execute_unknown_type_logs_warning_and_does_not_raise(monkeypatch, caplog):
    monkeypatch.setattr(registry, "_REGISTRY", {})

    with caplog.at_level(logging.WARNING):
        registry.execute("does_not_exist", {}, _flag())

    assert "does_not_exist" in caplog.text


def test_execute_swallows_action_exceptions(monkeypatch, caplog):
    monkeypatch.setattr(registry, "_REGISTRY", {})

    def _broken(target, flag):
        raise RuntimeError("device offline")

    registry.register("broken")(_broken)

    with caplog.at_level(logging.ERROR):
        registry.execute("broken", {}, _flag())  # must not raise

    assert "broken" in caplog.text
