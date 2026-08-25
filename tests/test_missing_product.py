from config.schema import FlagConfig, TaskConfig
from tasks.missing_product import MissingProductAnalyzer
from vision.types import Detection

ZONE = {"name": "shelf_1", "polygon": [[0, 0], [10, 0], [10, 10], [0, 10]], "expected_class": "bottle"}


def _bottle_in_zone():
    return Detection(class_name="bottle", confidence=0.9, bbox=(2, 2, 6, 6))


def _config(**params):
    return TaskConfig(type="missing_product", params=params, flags=[
        FlagConfig(id="missing_product", enabled=True, severity="warning", notify=["log"]),
    ])


def _clock(monkeypatch, module, start=1000.0):
    box = {"now": start}
    monkeypatch.setattr(module.time, "time", lambda: box["now"])
    return box


def test_no_flag_when_expected_product_present(monkeypatch):
    config = _config(zones=[ZONE], absence_dwell_seconds=10)
    analyzer = MissingProductAnalyzer("cam1", config)
    import tasks.missing_product as mod
    _clock(monkeypatch, mod)

    flags = analyzer.analyze(None, [_bottle_in_zone()], [])

    assert flags == []


def test_no_flag_before_absence_dwell_elapses(monkeypatch):
    config = _config(zones=[ZONE], absence_dwell_seconds=10)
    analyzer = MissingProductAnalyzer("cam1", config)
    import tasks.missing_product as mod
    clock = _clock(monkeypatch, mod)

    analyzer.analyze(None, [], [])  # zone empty, timer starts
    clock["now"] += 5
    flags = analyzer.analyze(None, [], [])

    assert flags == []


def test_flag_emitted_after_absence_dwell_elapses(monkeypatch):
    config = _config(zones=[ZONE], absence_dwell_seconds=10)
    analyzer = MissingProductAnalyzer("cam1", config)
    import tasks.missing_product as mod
    clock = _clock(monkeypatch, mod)

    analyzer.analyze(None, [], [])
    clock["now"] += 11
    flags = analyzer.analyze(None, [], [])

    assert len(flags) == 1
    assert flags[0].flag_id == "missing_product"
    assert "shelf_1" in flags[0].message


def test_product_reappearing_resets_absence_timer(monkeypatch):
    config = _config(zones=[ZONE], absence_dwell_seconds=10)
    analyzer = MissingProductAnalyzer("cam1", config)
    import tasks.missing_product as mod
    clock = _clock(monkeypatch, mod)

    analyzer.analyze(None, [], [])  # missing starts
    clock["now"] += 6
    analyzer.analyze(None, [_bottle_in_zone()], [])  # reappears, resets
    clock["now"] += 6  # would have tripped 10s if not reset
    flags = analyzer.analyze(None, [], [])

    assert flags == []


def test_product_of_wrong_class_does_not_satisfy_zone():
    config = _config(zones=[ZONE], absence_dwell_seconds=0)
    analyzer = MissingProductAnalyzer("cam1", config)

    wrong_class = Detection(class_name="cup", confidence=0.9, bbox=(2, 2, 6, 6))
    flags = analyzer.analyze(None, [wrong_class], [])

    assert len(flags) == 1
    assert flags[0].flag_id == "missing_product"


def test_flag_disabled_in_config(monkeypatch):
    config = TaskConfig(
        type="missing_product",
        params={"zones": [ZONE], "absence_dwell_seconds": 0},
        flags=[FlagConfig(id="missing_product", enabled=False)],
    )
    analyzer = MissingProductAnalyzer("cam1", config)

    flags = analyzer.analyze(None, [], [])

    assert flags == []
