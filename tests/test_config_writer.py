from config.loader import load_tasks_config
from config.writer import TasksYamlWriter

SAMPLE = """\
# comentário no topo do arquivo — deve sobreviver ao round-trip
cameras:
  cam1:
    tasks:
      - type: item_counting
        detect_fps: 5
        params:
          counting_line: {p1: [10, 0], p2: [10, 100]}  # comentário inline
        flags:
          - id: count_threshold
            enabled: true
            severity: warning
            notify: [log]
"""


def test_load_preserves_top_level_comment(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)

    writer = TasksYamlWriter(str(path))
    writer.save()  # round-trip write-back with no changes

    content = path.read_text()
    assert "comentário no topo do arquivo" in content
    assert "comentário inline" in content


def test_set_task_params_updates_only_that_field(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))

    writer.set_task_params("cam1", 0, {"counting_line": {"p1": [20, 0], "p2": [20, 200]}, "direction": "any"})

    reloaded = TasksYamlWriter(str(path))
    tasks = reloaded.get_tasks("cam1")
    assert tasks[0]["params"]["counting_line"]["p1"] == [20, 0]
    assert tasks[0]["params"]["direction"] == "any"
    assert tasks[0]["type"] == "item_counting"  # untouched


def test_add_task_to_existing_camera(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))

    writer.add_task("cam1", "missing_product", detect_fps=3.0, params={"zones": []})

    tasks_by_camera = load_tasks_config(str(path))
    assert len(tasks_by_camera["cam1"]) == 2
    assert tasks_by_camera["cam1"][1].type == "missing_product"
    assert tasks_by_camera["cam1"][1].detect_fps == 3.0


def test_add_task_to_new_camera(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))

    writer.add_task("cam2", "ppe_compliance", model="ppe.pt", params={"required_ppe": ["helmet"]})

    tasks_by_camera = load_tasks_config(str(path))
    assert tasks_by_camera["cam2"][0].type == "ppe_compliance"
    assert tasks_by_camera["cam2"][0].model == "ppe.pt"


def test_remove_task(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))
    writer.add_task("cam1", "missing_product", params={"zones": []})

    writer.remove_task("cam1", 0)  # removes the original item_counting task

    tasks_by_camera = load_tasks_config(str(path))
    assert len(tasks_by_camera["cam1"]) == 1
    assert tasks_by_camera["cam1"][0].type == "missing_product"


def test_set_flag_updates_existing_flag(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))

    writer.set_flag("cam1", 0, "count_threshold", enabled=False, severity="critical")

    tasks_by_camera = load_tasks_config(str(path))
    flag = tasks_by_camera["cam1"][0].flags[0]
    assert flag.enabled is False
    assert flag.severity == "critical"
    assert flag.notify == ["log"]  # untouched


def test_set_flag_adds_new_flag_if_missing(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(SAMPLE)
    writer = TasksYamlWriter(str(path))

    writer.set_flag("cam1", 0, "new_flag", enabled=True, severity="info", notify=["desktop"])

    tasks_by_camera = load_tasks_config(str(path))
    flags_by_id = {f.id: f for f in tasks_by_camera["cam1"][0].flags}
    assert "new_flag" in flags_by_id
    assert flags_by_id["new_flag"].notify == ["desktop"]


def test_writer_on_missing_file_starts_empty(tmp_path):
    path = tmp_path / "does_not_exist.yaml"
    writer = TasksYamlWriter(str(path))

    assert writer.camera_ids() == []

    writer.add_task("cam1", "item_counting", params={"counting_line": {"p1": [0, 0], "p2": [0, 1]}})

    tasks_by_camera = load_tasks_config(str(path))
    assert tasks_by_camera["cam1"][0].type == "item_counting"
