from vision.tracker import Tracker
from vision.types import Detection


def _det(class_name, bbox, confidence=0.9):
    return Detection(class_name=class_name, confidence=confidence, bbox=bbox)


def test_first_frame_assigns_new_ids():
    tracker = Tracker()

    tracks = tracker.update([_det("box", (0, 0, 10, 10)), _det("box", (100, 100, 110, 110))])

    assert len(tracks) == 2
    assert {t.track_id for t in tracks} == {1, 2}


def test_matching_detection_keeps_same_id_across_frames():
    tracker = Tracker()

    tracker.update([_det("box", (0, 0, 10, 10))])
    tracks = tracker.update([_det("box", (1, 1, 11, 11))])  # small shift, high IOU

    assert len(tracks) == 1
    assert tracks[0].track_id == 1


def test_different_class_does_not_match_even_with_same_bbox():
    tracker = Tracker()

    tracker.update([_det("box", (0, 0, 10, 10))])
    tracks = tracker.update([_det("person", (0, 0, 10, 10))])

    assert len(tracks) == 1
    assert tracks[0].track_id == 2  # new track, not reused


def test_track_survives_brief_occlusion_within_max_misses():
    tracker = Tracker(max_misses=2)

    tracker.update([_det("box", (0, 0, 10, 10))])
    tracker.update([])  # miss 1 (object briefly not detected)
    tracks = tracker.update([_det("box", (1, 1, 11, 11))])  # reappears

    assert len(tracks) == 1
    assert tracks[0].track_id == 1


def test_track_dropped_after_exceeding_max_misses():
    tracker = Tracker(max_misses=1)

    tracker.update([_det("box", (0, 0, 10, 10))])
    tracker.update([])  # miss 1
    tracker.update([])  # miss 2, exceeds max_misses=1 -> dropped
    tracks = tracker.update([_det("box", (0, 0, 10, 10))])

    assert tracks[0].track_id == 2  # got a fresh id, old one was dropped


def test_low_iou_creates_new_track_instead_of_matching():
    tracker = Tracker(iou_threshold=0.5)

    tracker.update([_det("box", (0, 0, 10, 10))])
    # No overlap at all: update() only reports tracks seen this frame (matched or
    # brand new) — the old track isn't dropped yet, just not returned until it's
    # seen again (within max_misses) or ages out.
    tracks = tracker.update([_det("box", (50, 50, 60, 60))])

    assert len(tracks) == 1
    assert tracks[0].track_id == 2
