from config.schema import FlagConfig, TaskConfig
from tasks.ppe_compliance import PPEComplianceAnalyzer
from vision.types import Track


def _person(track_id=1, bbox=(0, 0, 20, 40)):
    return Track(class_name="person", confidence=0.9, bbox=bbox, track_id=track_id)


def _helmet(track_id=2, bbox=(0, 0, 20, 10)):
    return Track(class_name="helmet", confidence=0.9, bbox=bbox, track_id=track_id)


def _config(**params):
    return TaskConfig(type="ppe_compliance", params=params, flags=[
        FlagConfig(id="missing_ppe", enabled=True, severity="critical", notify=["log"]),
    ])


def _clock(monkeypatch, module, start=1000.0):
    box = {"now": start}
    monkeypatch.setattr(module.time, "time", lambda: box["now"])
    return box


def test_no_flag_before_dwell_elapses(monkeypatch):
    config = _config(required_ppe=["helmet"], missing_ppe_dwell_seconds=30)
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    clock = _clock(monkeypatch, mod)

    flags = analyzer.analyze(None, [], [_person()])  # no helmet present at all

    assert flags == []
    clock["now"] += 10  # still under 30s dwell
    flags = analyzer.analyze(None, [], [_person()])
    assert flags == []


def test_flag_emitted_after_dwell_elapses(monkeypatch):
    config = _config(required_ppe=["helmet"], missing_ppe_dwell_seconds=30)
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    clock = _clock(monkeypatch, mod)

    analyzer.analyze(None, [], [_person()])
    clock["now"] += 31
    flags = analyzer.analyze(None, [], [_person()])

    assert len(flags) == 1
    assert flags[0].flag_id == "missing_ppe"
    assert "helmet" in flags[0].message


def test_no_flag_when_required_ppe_present_and_overlapping(monkeypatch):
    config = _config(required_ppe=["helmet"], missing_ppe_dwell_seconds=30)
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    clock = _clock(monkeypatch, mod)

    person = _person(bbox=(0, 0, 20, 40))
    helmet = _helmet(bbox=(0, 0, 20, 10))  # overlaps the person's bbox

    analyzer.analyze(None, [], [person, helmet])
    clock["now"] += 60
    flags = analyzer.analyze(None, [], [person, helmet])

    assert flags == []


def test_compliance_resets_dwell_timer(monkeypatch):
    config = _config(required_ppe=["helmet"], missing_ppe_dwell_seconds=30)
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    clock = _clock(monkeypatch, mod)

    person = _person()
    helmet = _helmet()

    analyzer.analyze(None, [], [person])  # missing starts
    clock["now"] += 20
    analyzer.analyze(None, [], [person, helmet])  # becomes compliant, resets timer
    clock["now"] += 20  # would have tripped 30s if the timer hadn't reset
    flags = analyzer.analyze(None, [], [person])

    assert flags == []  # only 20s since it went missing again, not 30s


def test_zone_filtering_ignores_person_outside_zone(monkeypatch):
    config = _config(
        required_ppe=["helmet"],
        missing_ppe_dwell_seconds=0,
        zones=[{"name": "work_area", "polygon": [[100, 100], [200, 100], [200, 200], [100, 200]]}],
    )
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    _clock(monkeypatch, mod)

    person_outside = _person(bbox=(0, 0, 20, 40))  # center (10, 20), outside the zone
    flags = analyzer.analyze(None, [], [person_outside])

    assert flags == []


def test_flag_disabled_in_config(monkeypatch):
    config = TaskConfig(
        type="ppe_compliance",
        params={"required_ppe": ["helmet"], "missing_ppe_dwell_seconds": 0},
        flags=[FlagConfig(id="missing_ppe", enabled=False)],
    )
    analyzer = PPEComplianceAnalyzer("cam1", config)
    import tasks.ppe_compliance as mod
    _clock(monkeypatch, mod)

    flags = analyzer.analyze(None, [], [_person()])

    assert flags == []
