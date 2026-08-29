import pytest

from config.schema import TaskConfig
from tasks.model_kinds import TASK_MODEL_KIND, model_kind_for
from vision.model_kind import ModelKind, kind_from_ultralytics_task


def test_every_ultralytics_task_maps_to_a_kind():
    for task in ("detect", "obb", "segment", "pose", "classify"):
        assert isinstance(kind_from_ultralytics_task(task), ModelKind)


def test_unrecognized_ultralytics_task_raises():
    with pytest.raises(ValueError):
        kind_from_ultralytics_task("something-else")


def test_registry_lookup_for_known_task_type():
    assert model_kind_for(TaskConfig(type="ppe_compliance")) == ModelKind.DETECTION
    assert model_kind_for(TaskConfig(type="face_id")) == ModelKind.NONE
    assert model_kind_for(TaskConfig(type="print_monitor")) == ModelKind.SEGMENTATION


def test_unknown_task_type_defaults_to_detection():
    assert model_kind_for(TaskConfig(type="some_future_task")) == ModelKind.DETECTION


def test_explicit_model_type_overrides_registry():
    task = TaskConfig(type="ppe_compliance", model_type="segmentation")
    assert model_kind_for(task) == ModelKind.SEGMENTATION


def test_task_model_kind_has_no_typos():
    for task_type, kind in TASK_MODEL_KIND.items():
        assert isinstance(task_type, str)
        assert isinstance(kind, ModelKind)
