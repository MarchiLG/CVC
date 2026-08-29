import pytest

from config.loader import load_triggers_config
from config.triggers_writer import TriggersYamlWriter

SAMPLE = """\
# comment at the top of the file - must survive the round-trip
mode: ask
rules:
  - id: jam-stops-conveyor
    enabled: true
    condition: {task_type: item_counting, flag_id: count_threshold}  # inline comment
    actions:
      - type: modbus_tcp
        target: {host: "192.168.1.50", port: 502, register: 100, value: 1}
"""


def test_load_preserves_top_level_comment(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)

    writer = TriggersYamlWriter(str(path))
    writer.save()

    content = path.read_text()
    assert "comment at the top of the file" in content
    assert "inline comment" in content


def test_set_mode_updates_only_that_field(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    writer.set_mode("auto")

    reloaded = TriggersYamlWriter(str(path))
    assert reloaded.get_mode() == "auto"
    assert reloaded.get_rules()[0]["id"] == "jam-stops-conveyor"  # untouched


def test_add_rule(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    writer.add_rule(
        "new-rule",
        condition={"camera_id": "cam2"},
        actions=[{"type": "mqtt", "target": {"host": "h", "topic": "t"}}],
    )

    settings = load_triggers_config(str(path))
    assert len(settings.rules) == 2
    assert settings.rules[1].id == "new-rule"
    assert settings.rules[1].condition.camera_id == "cam2"
    assert settings.rules[1].actions[0].type == "mqtt"


def test_update_rule_toggles_enabled_without_touching_condition(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    writer.update_rule("jam-stops-conveyor", enabled=False)

    settings = load_triggers_config(str(path))
    rule = settings.rules[0]
    assert rule.enabled is False
    assert rule.condition.task_type == "item_counting"  # untouched


def test_update_unknown_rule_raises(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    with pytest.raises(KeyError):
        writer.update_rule("does-not-exist", enabled=False)


def test_remove_rule(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    writer.remove_rule("jam-stops-conveyor")

    settings = load_triggers_config(str(path))
    assert settings.rules == []


def test_remove_unknown_rule_raises(tmp_path):
    path = tmp_path / "Triggers.yaml"
    path.write_text(SAMPLE)
    writer = TriggersYamlWriter(str(path))

    with pytest.raises(KeyError):
        writer.remove_rule("does-not-exist")


def test_writer_on_missing_file_starts_with_defaults(tmp_path):
    path = tmp_path / "does_not_exist.yaml"
    writer = TriggersYamlWriter(str(path))

    assert writer.get_mode() == "ask"
    assert list(writer.get_rules()) == []

    writer.add_rule("r1", condition={}, actions=[{"type": "http_webhook", "target": {"url": "http://x"}}])

    settings = load_triggers_config(str(path))
    assert settings.rules[0].id == "r1"
