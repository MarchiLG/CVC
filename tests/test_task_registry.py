import pytest

from config.schema import TaskConfig
from notify.flag import Flag
from tasks import registry
from tasks.base import TaskAnalyzer


class _DummyAnalyzer(TaskAnalyzer):
    type = "dummy_test_task"

    def analyze(self, frame, detections, tracks):
        return [Flag(camera_id=self.camera_id, task_type=self.type, flag_id="dummy")]


def test_register_and_create():
    registry.register("dummy_test_task")(_DummyAnalyzer)

    analyzer = registry.create("dummy_test_task", "cam1", TaskConfig(type="dummy_test_task"))

    assert isinstance(analyzer, _DummyAnalyzer)
    assert analyzer.camera_id == "cam1"
    assert "dummy_test_task" in registry.available_types()


def test_create_unknown_type_raises():
    with pytest.raises(ValueError):
        registry.create("does_not_exist", "cam1", TaskConfig(type="does_not_exist"))
