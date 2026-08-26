"""
face_id.py

Face recognition: runs InsightFace over the frame (independently of the
pipeline's YOLO detector — the raw frame is already available in the
TaskAnalyzer.analyze signature) and, for each face, looks up the
closest matching employee in the database
(db/repository.find_best_match). If nobody matches above the threshold
and log_unknown is on, emits the "unknown_face" Flag.

params expected in tasks.yaml:
    match_threshold: float (defaults to 0.45)
    log_unknown: bool (defaults to true)
    device: "auto" | "cpu" | "cuda" (defaults to "auto")
    model_pack: override for the InsightFace pack (optional; otherwise
        uses the device default — buffalo_l/buffalo_s)
"""

from notify.flag import Flag
from vision.device import default_face_model_for_device, resolve_device
from vision.face.recognizer import get_face_recognizer

from .base import TaskAnalyzer
from .registry import register

_DEFAULT_THRESHOLD = 0.45


@register("face_id")
class FaceIDAnalyzer(TaskAnalyzer):
    type = "face_id"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.match_threshold = config.params.get("match_threshold", _DEFAULT_THRESHOLD)
        self.log_unknown = config.params.get("log_unknown", True)

        device = resolve_device(config.params.get("device", "auto"))
        model_pack = config.params.get("model_pack") or default_face_model_for_device(device)
        self._recognizer = get_face_recognizer(model_pack)

    def analyze(self, frame, detections, tracks):
        if frame is None or not self.log_unknown:
            return []

        flag_config = self.flag_config("unknown_face")
        if flag_config is None or not flag_config.enabled:
            return []

        from db import repository
        from db.session import get_session

        flags: list[Flag] = []
        session = get_session()
        try:
            for face in self._recognizer.analyze(frame):
                employee, score = repository.find_best_match(session, face.embedding, self.match_threshold)
                if employee is not None:
                    continue
                flags.append(Flag(
                    camera_id=self.camera_id,
                    task_type=self.type,
                    flag_id="unknown_face",
                    severity=flag_config.severity,
                    message=f"Unrecognized face (similarity {score:.2f})",
                    notify=flag_config.notify,
                    message_key="flag.unknown_face",
                    message_params={"score": f"{score:.2f}"},
                ))
        finally:
            session.close()

        return flags
