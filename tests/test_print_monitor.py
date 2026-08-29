"""
Drives PrintMonitorAnalyzer by hand-setting `self.model_result` to a
ModelResult carrying synthetic segmentation masks — no real YOLO model
needed, which is the point of the ModelResult abstraction added in
Phase 1 (vision/results.py).
"""

import numpy as np

from config.schema import FlagConfig, TaskConfig
from tasks.print_monitor import PrintMonitorAnalyzer, _mask_area, _shape_irregularity
from vision.model_kind import ModelKind
from vision.results import ModelResult, SegmentationInstance


def _config(**params):
    return TaskConfig(type="print_monitor", params=params, flags=[
        FlagConfig(id="possible_failed_print", enabled=True, severity="warning", notify=["log"]),
    ])


def _circle_mask(radius, size=200):
    mask = np.zeros((size, size), dtype=np.uint8)
    yy, xx = np.ogrid[:size, :size]
    center = size // 2
    mask[(yy - center) ** 2 + (xx - center) ** 2 <= radius ** 2] = 1
    return mask


def _jagged_mask(size=200):
    """A handful of disconnected small blobs — much higher perimeter
    per unit area than a single compact shape, so _shape_irregularity
    should read high even at ordinary total area."""
    mask = np.zeros((size, size), dtype=np.uint8)
    for cx, cy in [(20, 20), (20, 180), (180, 20), (180, 180), (100, 20), (20, 100)]:
        mask[max(0, cy - 3):cy + 3, max(0, cx - 3):cx + 3] = 1
    return mask


def _feed(analyzer, mask):
    analyzer.model_result = ModelResult(
        kind=ModelKind.SEGMENTATION,
        detections=[SegmentationInstance(class_name="print", confidence=0.9, bbox=(0, 0, 1, 1), mask=mask)],
    )
    return analyzer.analyze(frame="fake-frame", detections=[], tracks=[])


def test_no_model_result_returns_no_flags():
    analyzer = PrintMonitorAnalyzer("cam1", _config())
    assert analyzer.analyze(frame="fake-frame", detections=[], tracks=[]) == []


def test_no_matching_class_returns_no_flags():
    analyzer = PrintMonitorAnalyzer("cam1", _config())
    analyzer.model_result = ModelResult(
        kind=ModelKind.SEGMENTATION,
        detections=[SegmentationInstance(class_name="something_else", confidence=0.9, bbox=(0, 0, 1, 1), mask=_circle_mask(20))],
    )
    assert analyzer.analyze(frame="fake-frame", detections=[], tracks=[]) == []


def test_stable_mask_never_flags():
    analyzer = PrintMonitorAnalyzer("cam1", _config(min_history_before_flagging=5, window_size=10))

    flags = []
    for _ in range(20):
        flags = _feed(analyzer, _circle_mask(30))

    assert flags == []


def test_sudden_area_growth_flags_with_ratio():
    analyzer = PrintMonitorAnalyzer("cam1", _config(min_history_before_flagging=5, window_size=10))

    for _ in range(10):
        _feed(analyzer, _circle_mask(20))

    flags = _feed(analyzer, _circle_mask(60))  # area grows by (60/20)^2 = 9x

    assert len(flags) == 1
    assert flags[0].flag_id == "possible_failed_print"
    assert float(flags[0].message_params["area_ratio"]) > 1.6


def test_irregular_shape_flags_even_at_normal_area():
    analyzer = PrintMonitorAnalyzer("cam1", _config(min_history_before_flagging=5, window_size=10, area_growth_threshold=100.0))

    stable_mask = _circle_mask(30)
    for _ in range(10):
        _feed(analyzer, stable_mask)

    jagged = _jagged_mask()
    # Make the jagged mask's total area close to the stable one, so this
    # only trips the irregularity path, not the area-growth path.
    flags = _feed(analyzer, jagged)

    assert len(flags) == 1
    assert float(flags[0].message_params["irregularity"]) >= 0.35


def test_below_warmup_never_flags_regardless_of_change():
    analyzer = PrintMonitorAnalyzer("cam1", _config(min_history_before_flagging=50, window_size=10))

    for _ in range(5):
        _feed(analyzer, _circle_mask(20))
    flags = _feed(analyzer, _circle_mask(100))

    assert flags == []


def test_disabled_flag_config_suppresses_flag():
    config = TaskConfig(
        type="print_monitor",
        params={"min_history_before_flagging": 5, "window_size": 10},
        flags=[FlagConfig(id="possible_failed_print", enabled=False)],
    )
    analyzer = PrintMonitorAnalyzer("cam1", config)

    for _ in range(10):
        _feed(analyzer, _circle_mask(20))
    flags = _feed(analyzer, _circle_mask(80))

    assert flags == []


def test_mask_area_counts_nonzero_pixels():
    mask = np.zeros((10, 10), dtype=np.uint8)
    mask[0:2, 0:5] = 1  # 10 pixels
    assert _mask_area(mask) == 10.0


def test_shape_irregularity_low_for_circle_high_for_jagged():
    circle_irregularity = _shape_irregularity(_circle_mask(50))
    jagged_irregularity = _shape_irregularity(_jagged_mask())

    assert circle_irregularity < 0.2
    assert jagged_irregularity > circle_irregularity


def test_shape_irregularity_zero_for_empty_mask():
    assert _shape_irregularity(np.zeros((50, 50), dtype=np.uint8)) == 0.0
