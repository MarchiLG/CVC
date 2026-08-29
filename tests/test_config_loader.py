import pytest

from config.loader import ConfigError, load_app_config, load_cameras_config, load_tasks_config, load_triggers_config


def test_load_cameras_config_expands_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CAM1_URL", "rtsp://example/1")
    cameras_yaml = tmp_path / "cameras.yaml"
    cameras_yaml.write_text(
        "cameras:\n"
        "  - id: cam1\n"
        "    name: C1\n"
        "    url: \"${CAM1_URL}\"\n"
        "    enabled: true\n"
    )

    cameras = load_cameras_config(str(cameras_yaml))

    assert len(cameras) == 1
    assert cameras[0].id == "cam1"
    assert cameras[0].url == "rtsp://example/1"
    assert cameras[0].enabled is True


def test_load_cameras_config_missing_env_var_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("CAM_MISSING", raising=False)
    cameras_yaml = tmp_path / "cameras.yaml"
    cameras_yaml.write_text(
        "cameras:\n"
        "  - id: cam1\n"
        "    name: C1\n"
        "    url: \"${CAM_MISSING}\"\n"
    )

    with pytest.raises(ConfigError):
        load_cameras_config(str(cameras_yaml))


def test_load_tasks_config_missing_file_returns_empty(tmp_path):
    assert load_tasks_config(str(tmp_path / "does_not_exist.yaml")) == {}


def test_load_tasks_config_parses_tasks_and_flags(tmp_path):
    tasks_yaml = tmp_path / "tasks.yaml"
    tasks_yaml.write_text(
        "cameras:\n"
        "  cam1:\n"
        "    tasks:\n"
        "      - type: item_counting\n"
        "        model: yolov8n.pt\n"
        "        detect_fps: 5\n"
        "        params:\n"
        "          direction: down\n"
        "        flags:\n"
        "          - id: count_threshold\n"
        "            enabled: false\n"
    )

    tasks_by_camera = load_tasks_config(str(tasks_yaml))

    assert list(tasks_by_camera.keys()) == ["cam1"]
    [task] = tasks_by_camera["cam1"]
    assert task.type == "item_counting"
    assert task.model == "yolov8n.pt"
    assert task.detect_fps == 5
    assert task.params == {"direction": "down"}
    assert task.flags[0].id == "count_threshold"
    assert task.flags[0].enabled is False


def test_load_triggers_config_missing_file_returns_defaults(tmp_path):
    settings = load_triggers_config(str(tmp_path / "does_not_exist.yaml"))
    assert settings.mode == "ask"
    assert settings.rules == []


def test_load_triggers_config_parses_rules(tmp_path):
    triggers_yaml = tmp_path / "Triggers.yaml"
    triggers_yaml.write_text(
        "mode: auto\n"
        "rules:\n"
        "  - id: jam-stops-conveyor\n"
        "    enabled: true\n"
        "    condition: {task_type: item_counting, flag_id: count_threshold}\n"
        "    actions:\n"
        "      - type: modbus_tcp\n"
        "        target: {host: 192.168.1.50, port: 502, register: 100, value: 1}\n"
    )

    settings = load_triggers_config(str(triggers_yaml))

    assert settings.mode == "auto"
    [rule] = settings.rules
    assert rule.id == "jam-stops-conveyor"
    assert rule.enabled is True
    assert rule.condition.task_type == "item_counting"
    assert rule.condition.flag_id == "count_threshold"
    assert rule.condition.camera_id is None
    assert rule.actions[0].type == "modbus_tcp"
    assert rule.actions[0].target == {"host": "192.168.1.50", "port": 502, "register": 100, "value": 1}


def test_load_app_config_missing_file_returns_defaults(tmp_path):
    settings = load_app_config(str(tmp_path / "does_not_exist.yaml"))
    assert settings.vision.device == "auto"
    assert settings.db.enabled is False
    assert settings.llm.enabled is False


def test_load_app_config_parses_overrides(tmp_path):
    app_yaml = tmp_path / "app.yaml"
    app_yaml.write_text(
        "vision:\n"
        "  device: cuda\n"
        "llm:\n"
        "  enabled: true\n"
        "  model: qwen2.5:1.5b\n"
    )

    settings = load_app_config(str(app_yaml))

    assert settings.vision.device == "cuda"
    assert settings.llm.enabled is True
    assert settings.llm.model == "qwen2.5:1.5b"
