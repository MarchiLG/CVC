"""
writer.py

Writes tasks.yaml preserving comments/formatting (via ruamel.yaml in
round-trip mode) — used by the calibration and settings screens of both
interfaces, which edit parameters of existing tasks or add/remove tasks
without rewriting the file from scratch the way yaml.safe_dump would.
"""

import os

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


class TasksYamlWriter:
    def __init__(self, path: str):
        self.path = path
        self._yaml = YAML()
        self._yaml.preserve_quotes = True
        self._yaml.indent(mapping=2, sequence=4, offset=2)
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = self._yaml.load(f) or CommentedMap()
        else:
            self.data = CommentedMap()

        if "cameras" not in self.data:
            self.data["cameras"] = CommentedMap()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            self._yaml.dump(self.data, f)

    def camera_ids(self) -> list[str]:
        return list(self.data["cameras"].keys())

    def get_tasks(self, camera_id: str) -> CommentedSeq:
        camera_entry = self.data["cameras"].get(camera_id)
        if camera_entry is None or "tasks" not in camera_entry:
            return CommentedSeq()
        return camera_entry["tasks"]

    def set_task_params(self, camera_id: str, task_index: int, params: dict):
        tasks = self.get_tasks(camera_id)
        tasks[task_index]["params"] = params
        self.save()

    def set_task_detect_fps(self, camera_id: str, task_index: int, detect_fps: float):
        tasks = self.get_tasks(camera_id)
        tasks[task_index]["detect_fps"] = detect_fps
        self.save()

    def set_task_model(self, camera_id: str, task_index: int, model: str | None, model_type: str | None = None):
        tasks = self.get_tasks(camera_id)
        task = tasks[task_index]
        if model:
            task["model"] = model
        elif "model" in task:
            del task["model"]
        if model_type:
            task["model_type"] = model_type
        elif "model_type" in task:
            del task["model_type"]
        self.save()

    def add_task(
        self,
        camera_id: str,
        task_type: str,
        model: str | None = None,
        model_type: str | None = None,
        detect_fps: float = 5.0,
        params: dict | None = None,
        flags: list[dict] | None = None,
    ):
        cameras = self.data["cameras"]
        if camera_id not in cameras:
            cameras[camera_id] = CommentedMap({"tasks": CommentedSeq()})
        camera_entry = cameras[camera_id]
        if "tasks" not in camera_entry:
            camera_entry["tasks"] = CommentedSeq()

        new_task = CommentedMap()
        new_task["type"] = task_type
        if model:
            new_task["model"] = model
        if model_type:
            new_task["model_type"] = model_type
        new_task["detect_fps"] = detect_fps
        new_task["params"] = params or {}
        new_task["flags"] = flags or []
        camera_entry["tasks"].append(new_task)
        self.save()

    def remove_task(self, camera_id: str, task_index: int):
        tasks = self.get_tasks(camera_id)
        del tasks[task_index]
        self.save()

    def set_flag(
        self,
        camera_id: str,
        task_index: int,
        flag_id: str,
        enabled: bool | None = None,
        severity: str | None = None,
        notify: list[str] | None = None,
    ):
        tasks = self.get_tasks(camera_id)
        task = tasks[task_index]
        flags = task.setdefault("flags", CommentedSeq())

        target = None
        for flag in flags:
            if flag.get("id") == flag_id:
                target = flag
                break
        if target is None:
            target = CommentedMap({"id": flag_id})
            flags.append(target)

        if enabled is not None:
            target["enabled"] = enabled
        if severity is not None:
            target["severity"] = severity
        if notify is not None:
            target["notify"] = list(notify)

        self.save()
