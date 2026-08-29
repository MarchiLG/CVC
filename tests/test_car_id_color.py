import numpy as np

from vision.car_id import dominant_color


def _solid_bgr_patch(bgr, size=20):
    patch = np.zeros((size, size, 3), dtype=np.uint8)
    patch[:, :] = bgr
    return patch


def test_dominant_color_of_solid_red_patch():
    assert dominant_color(_solid_bgr_patch((0, 0, 255))) == "red"  # BGR red


def test_dominant_color_of_solid_blue_patch():
    assert dominant_color(_solid_bgr_patch((255, 0, 0))) == "blue"  # BGR blue


def test_dominant_color_of_solid_white_patch():
    assert dominant_color(_solid_bgr_patch((255, 255, 255))) == "white"


def test_dominant_color_of_solid_black_patch():
    assert dominant_color(_solid_bgr_patch((0, 0, 0))) == "black"


def test_dominant_color_empty_crop_returns_empty_string():
    assert dominant_color(np.zeros((0, 0, 3), dtype=np.uint8)) == ""


def test_dominant_color_none_crop_returns_empty_string():
    assert dominant_color(None) == ""
