from config.schema import FlagConfig, TaskConfig
from tasks.treadmill_counter import ItemCountingAnalyzer
from vision.types import Track


def _track(track_id, x, class_name="person"):
    return Track(class_name=class_name, confidence=0.9, bbox=(x - 5, 0, x + 5, 10), track_id=track_id)


def _config(**params):
    return TaskConfig(type="item_counting", params=params, flags=[
        FlagConfig(id="count_threshold", enabled=True, severity="warning", notify=["log"]),
    ])


def _clock(monkeypatch, module, start=1000.0):
    box = {"now": start}
    monkeypatch.setattr(module.time, "time", lambda: box["now"])
    return box


def test_crossing_the_line_increments_count(monkeypatch):
    config = _config(counting_line={"p1": [10, -100], "p2": [10, 100]}, direction="any")
    analyzer = ItemCountingAnalyzer("cam1", config)
    import tasks.treadmill_counter as mod
    _clock(monkeypatch, mod)

    analyzer.analyze(None, [], [_track(1, x=0)])  # left of line
    analyzer.analyze(None, [], [_track(1, x=20)])  # crosses to the right

    assert analyzer.count == 1


def test_staying_on_same_side_does_not_count():
    config = _config(counting_line={"p1": [10, -100], "p2": [10, 100]}, direction="any")
    analyzer = ItemCountingAnalyzer("cam1", config)

    analyzer.analyze(None, [], [_track(1, x=0)])
    analyzer.analyze(None, [], [_track(1, x=1)])
    analyzer.analyze(None, [], [_track(1, x=2)])

    assert analyzer.count == 0


def test_direction_filter_ignores_wrong_way_crossings():
    config = _config(counting_line={"p1": [10, -100], "p2": [10, 100]}, direction="positive")
    analyzer = ItemCountingAnalyzer("cam1", config)

    # x=0 -> side +1, x=20 -> side -1 for this line's orientation (see geometry.line_side):
    # this movement is a "positive to negative" crossing, the opposite of the configured direction.
    analyzer.analyze(None, [], [_track(1, x=0)])
    analyzer.analyze(None, [], [_track(1, x=20)])

    assert analyzer.count == 0


def test_target_classes_filters_out_other_classes():
    config = _config(
        counting_line={"p1": [10, -100], "p2": [10, 100]}, direction="any", target_classes=["box"],
    )
    analyzer = ItemCountingAnalyzer("cam1", config)

    analyzer.analyze(None, [], [_track(1, x=0, class_name="person")])
    analyzer.analyze(None, [], [_track(1, x=20, class_name="person")])

    assert analyzer.count == 0


def test_no_threshold_flag_when_flag_not_configured():
    config = TaskConfig(
        type="item_counting",
        params={
            "counting_line": {"p1": [10, -100], "p2": [10, 100]},
            "min_count_per_window": 5,
            "window_seconds": 10,
        },
        flags=[],  # count_threshold not configured at all
    )
    analyzer = ItemCountingAnalyzer("cam1", config)

    flags = analyzer.analyze(None, [], [])

    assert flags == []


def test_threshold_flag_not_emitted_before_window_elapses(monkeypatch):
    import tasks.treadmill_counter as mod
    clock = _clock(monkeypatch, mod)  # patch time before constructing the analyzer (__init__ reads _started_at)

    config = _config(
        counting_line={"p1": [10, -100], "p2": [10, 100]},
        min_count_per_window=5,
        window_seconds=60,
    )
    analyzer = ItemCountingAnalyzer("cam1", config)

    clock["now"] += 10  # still within the window
    flags = analyzer.analyze(None, [], [])

    assert flags == []


def test_threshold_flag_emitted_after_window_with_low_count(monkeypatch):
    import tasks.treadmill_counter as mod
    clock = _clock(monkeypatch, mod)

    config = _config(
        counting_line={"p1": [10, -100], "p2": [10, 100]},
        min_count_per_window=5,
        window_seconds=60,
    )
    analyzer = ItemCountingAnalyzer("cam1", config)

    clock["now"] += 61  # past the window, zero crossings happened
    flags = analyzer.analyze(None, [], [])

    assert len(flags) == 1
    assert flags[0].flag_id == "count_threshold"
    assert flags[0].camera_id == "cam1"


def test_threshold_flag_disabled_in_config(monkeypatch):
    import tasks.treadmill_counter as mod
    clock = _clock(monkeypatch, mod)

    config = TaskConfig(
        type="item_counting",
        params={
            "counting_line": {"p1": [10, -100], "p2": [10, 100]},
            "min_count_per_window": 5,
            "window_seconds": 60,
        },
        flags=[FlagConfig(id="count_threshold", enabled=False)],
    )
    analyzer = ItemCountingAnalyzer("cam1", config)

    clock["now"] += 61
    flags = analyzer.analyze(None, [], [])

    assert flags == []
