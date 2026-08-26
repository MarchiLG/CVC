"""
Smoke test exercising the real InsightFace model (buffalo_s, CPU).
Skipped automatically if onnxruntime/insightface aren't installed.
"""

import numpy as np
import pytest

pytest.importorskip("onnxruntime")
pytest.importorskip("insightface")

from vision.face.recognizer import FaceRecognizer


def test_real_face_recognizer_loads_and_runs_on_blank_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    recognizer = FaceRecognizer(model_pack="buffalo_s")
    faces = recognizer.analyze(frame)

    assert isinstance(faces, list)
    assert faces == []  # blank frame has no faces, but must not crash
