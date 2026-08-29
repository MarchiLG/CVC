from vision import model_catalog
from vision.model_kind import ModelKind


def test_list_models_returns_empty_for_missing_folder(monkeypatch, tmp_path):
    monkeypatch.setattr(model_catalog, "MODELS_DIR", str(tmp_path))
    assert model_catalog.list_models(ModelKind.OBB) == []


def test_list_models_lists_and_sorts_checkpoints(monkeypatch, tmp_path):
    monkeypatch.setattr(model_catalog, "MODELS_DIR", str(tmp_path))
    kind_dir = tmp_path / "detection"
    kind_dir.mkdir()
    (kind_dir / "b.pt").touch()
    (kind_dir / "a.pt").touch()
    (kind_dir / ".hidden.pt").touch()

    assert model_catalog.list_models(ModelKind.DETECTION) == [
        "models/detection/a.pt",
        "models/detection/b.pt",
    ]


def test_scan_all_models_covers_every_kind_except_none(monkeypatch, tmp_path):
    monkeypatch.setattr(model_catalog, "MODELS_DIR", str(tmp_path))
    (tmp_path / "segmentation").mkdir()
    (tmp_path / "segmentation" / "seg.pt").touch()

    result = model_catalog.scan_all_models()

    assert set(result.keys()) == {"detection", "obb", "segmentation", "pose", "classification"}
    assert result["segmentation"] == ["models/segmentation/seg.pt"]
    assert result["obb"] == []
