"""
cameras_writer.py

Writes config/cameras.yaml preserving comments/formatting (ruamel.yaml
round-trip) -- the camera-registry counterpart of writer.py's
TasksYamlWriter. Used by the web UI's "Add camera" panel and per-camera
settings menu to add, edit or remove a camera without disturbing the
rest of the file.
"""

import os

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


class CamerasYamlWriter:
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
            self.data["cameras"] = CommentedSeq()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            self._yaml.dump(self.data, f)

    def find_index(self, camera_id: str) -> int | None:
        for index, entry in enumerate(self.data["cameras"]):
            if entry.get("id") == camera_id:
                return index
        return None

    def find(self, camera_id: str) -> CommentedMap | None:
        index = self.find_index(camera_id)
        return None if index is None else self.data["cameras"][index]

    def exists(self, camera_id: str) -> bool:
        return self.find_index(camera_id) is not None

    def list_entries(self) -> CommentedSeq:
        return self.data["cameras"]

    def add(self, camera_id: str, name: str, url_ref: str, enabled: bool = True) -> None:
        if self.exists(camera_id):
            raise ValueError(f"Camera '{camera_id}' already exists.")

        entry = CommentedMap()
        entry["id"] = camera_id
        entry["name"] = name
        entry["url"] = url_ref
        entry["enabled"] = enabled
        self.data["cameras"].append(entry)
        self.save()

    def update(
        self,
        camera_id: str,
        name: str | None = None,
        url_ref: str | None = None,
        enabled: bool | None = None,
    ) -> None:
        entry = self.find(camera_id)
        if entry is None:
            raise KeyError(camera_id)

        if name is not None:
            entry["name"] = name
        if url_ref is not None:
            entry["url"] = url_ref
        if enabled is not None:
            entry["enabled"] = enabled
        self.save()

    def remove(self, camera_id: str) -> None:
        index = self.find_index(camera_id)
        if index is None:
            raise KeyError(camera_id)
        del self.data["cameras"][index]
        self.save()
