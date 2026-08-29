"""
triggers_writer.py

Writes config/Triggers.yaml preserving comments/formatting (via
ruamel.yaml in round-trip mode) — same approach as writer.py's
TasksYamlWriter, used by the web UI's Triggers screen.
"""

import os

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq


class TriggersYamlWriter:
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

        if "mode" not in self.data:
            self.data["mode"] = "ask"
        if "rules" not in self.data:
            self.data["rules"] = CommentedSeq()

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            self._yaml.dump(self.data, f)

    def get_mode(self) -> str:
        return self.data.get("mode", "ask")

    def set_mode(self, mode: str):
        self.data["mode"] = mode
        self.save()

    def get_rules(self) -> CommentedSeq:
        return self.data["rules"]

    def find_rule_index(self, rule_id: str) -> int | None:
        for index, rule in enumerate(self.get_rules()):
            if rule.get("id") == rule_id:
                return index
        return None

    def add_rule(self, rule_id: str, condition: dict, actions: list[dict], enabled: bool = True):
        new_rule = CommentedMap()
        new_rule["id"] = rule_id
        new_rule["enabled"] = enabled
        new_rule["condition"] = CommentedMap(condition)
        new_rule["actions"] = CommentedSeq([CommentedMap(action) for action in actions])
        self.get_rules().append(new_rule)
        self.save()

    def update_rule(
        self,
        rule_id: str,
        enabled: bool | None = None,
        condition: dict | None = None,
        actions: list[dict] | None = None,
    ):
        index = self.find_rule_index(rule_id)
        if index is None:
            raise KeyError(f"No trigger rule with id '{rule_id}'")

        rule = self.get_rules()[index]
        if enabled is not None:
            rule["enabled"] = enabled
        if condition is not None:
            rule["condition"] = CommentedMap(condition)
        if actions is not None:
            rule["actions"] = CommentedSeq([CommentedMap(action) for action in actions])
        self.save()

    def remove_rule(self, rule_id: str):
        index = self.find_rule_index(rule_id)
        if index is None:
            raise KeyError(f"No trigger rule with id '{rule_id}'")
        del self.get_rules()[index]
        self.save()
