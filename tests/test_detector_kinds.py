"""
Feeds fake ultralytics.Results-shaped objects (plain SimpleNamespace/
list stand-ins, not a real model) through each of Detector's per-kind
parsers, so the kind-specific parsing logic is pinned down without
needing a real checkpoint.
"""

from types import SimpleNamespace

import numpy as np

from vision.detector import (
    _parse_classification,
    _parse_detect,
    _parse_obb,
    _parse_pose,
    _parse_segmentation,
)


class _TensorLike:
    """Stands in for a torch.Tensor: only the .cpu().numpy() chain the
    parsers actually call."""

    def __init__(self, array):
        self._array = np.asarray(array)

    def cpu(self):
        return self

    def numpy(self):
        return self._array


def _box(cls_id, confidence, xyxy):
    return SimpleNamespace(cls=[cls_id], conf=[confidence], xyxy=[xyxy])


class _FakeObb:
    """Stands in for ultralytics' OBB results container: needs len()
    (used by _parse_obb to know how many detections there are), on top
    of the per-index cls/conf/xyxyxyxy attributes."""

    def __init__(self, cls, conf, xyxyxyxy):
        self.cls = cls
        self.conf = conf
        self.xyxyxyxy = xyxyxyxy

    def __len__(self):
        return len(self.cls)


def test_parse_detect():
    result = SimpleNamespace(
        names={0: "person", 1: "car"},
        boxes=[_box(1, 0.9, (10.0, 20.0, 30.0, 40.0))],
    )

    detections = _parse_detect(result)

    assert len(detections) == 1
    assert detections[0].class_name == "car"
    assert detections[0].confidence == 0.9
    assert detections[0].bbox == (10.0, 20.0, 30.0, 40.0)


def test_parse_obb_computes_axis_aligned_envelope():
    corners = np.array([[10.0, 10.0], [30.0, 15.0], [25.0, 40.0], [5.0, 35.0]])
    result = SimpleNamespace(
        names={0: "ship"},
        obb=_FakeObb(cls=[0], conf=[0.8], xyxyxyxy=[corners]),
    )

    detections = _parse_obb(result)

    assert len(detections) == 1
    obb = detections[0]
    assert obb.class_name == "ship"
    assert obb.confidence == 0.8
    assert obb.corners == tuple(map(tuple, corners.tolist()))
    assert obb.bbox == (5.0, 10.0, 30.0, 40.0)  # (min x, min y, max x, max y)


def test_parse_obb_handles_no_detections():
    result = SimpleNamespace(names={}, obb=None)
    assert _parse_obb(result) == []


def test_parse_segmentation_resizes_mask_to_frame_shape():
    mask_small = np.ones((4, 4), dtype=np.float32)  # smaller than the "frame"
    result = SimpleNamespace(
        names={0: "print"},
        orig_shape=(8, 8),
        boxes=[_box(0, 0.75, (1.0, 1.0, 7.0, 7.0))],
        masks=SimpleNamespace(data=_TensorLike(mask_small[np.newaxis, ...])),
    )

    instances = _parse_segmentation(result)

    assert len(instances) == 1
    instance = instances[0]
    assert instance.class_name == "print"
    assert instance.bbox == (1.0, 1.0, 7.0, 7.0)
    assert instance.mask.shape == (8, 8)


def test_parse_segmentation_handles_no_masks():
    result = SimpleNamespace(names={}, orig_shape=(8, 8), boxes=[], masks=None)
    assert _parse_segmentation(result) == []


def test_parse_pose_extracts_keypoints():
    kpts = np.array([[[1.0, 2.0, 0.9], [3.0, 4.0, 0.8]]])  # one instance, 2 joints
    result = SimpleNamespace(
        names={0: "person"},
        boxes=[_box(0, 0.6, (0.0, 0.0, 10.0, 10.0))],
        keypoints=SimpleNamespace(data=_TensorLike(kpts)),
    )

    instances = _parse_pose(result)

    assert len(instances) == 1
    assert instances[0].keypoints == [(1.0, 2.0, 0.9), (3.0, 4.0, 0.8)]


def test_parse_classification_picks_top1():
    result = SimpleNamespace(
        names={0: "sedan", 1: "suv"},
        probs=SimpleNamespace(data=np.array([0.2, 0.8]), top1=1, top1conf=0.8),
    )

    classification = _parse_classification(result)

    assert classification.class_name == "suv"
    assert classification.confidence == 0.8
    assert classification.scores == {"sedan": 0.2, "suv": 0.8}
