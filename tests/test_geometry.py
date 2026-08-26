from tasks.geometry import bbox_center, bbox_overlaps, line_side, point_in_polygon


def test_bbox_center():
    assert bbox_center((0, 0, 10, 20)) == (5.0, 10.0)


def test_point_in_polygon_inside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), square) is True


def test_point_in_polygon_outside():
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((15, 5), square) is False


def test_line_side_opposite_sides_have_opposite_signs():
    p1, p2 = (0, 0), (10, 0)  # horizontal line along x-axis
    above = line_side((5, -5), p1, p2)
    below = line_side((5, 5), p1, p2)
    assert above != below
    assert above != 0
    assert below != 0


def test_line_side_on_the_line_is_zero():
    p1, p2 = (0, 0), (10, 0)
    assert line_side((5, 0), p1, p2) == 0


def test_bbox_overlaps_true_for_intersecting_boxes():
    assert bbox_overlaps((0, 0, 10, 10), (5, 5, 15, 15)) is True


def test_bbox_overlaps_false_for_disjoint_boxes():
    assert bbox_overlaps((0, 0, 10, 10), (20, 20, 30, 30)) is False
