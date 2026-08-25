"""
face_id.py

Reconhecimento facial: roda o InsightFace (independente do detector
YOLO da pipeline — o frame bruto já vem disponível na assinatura de
TaskAnalyzer.analyze) sobre o frame, e para cada rosto busca o
funcionário mais parecido no banco (db/repository.find_best_match).
Se ninguém bater acima do limiar e log_unknown estiver ativo, emite o
Flag "unknown_face".

params esperados em tasks.yaml:
    match_threshold: float (default 0.45)
    log_unknown: bool (default true)
    device: "auto" | "cpu" | "cuda" (default "auto")
    model_pack: override do pacote InsightFace (opcional; senão usa o
        padrão do device — buffalo_l/buffalo_s)
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
                    message=f"Rosto não reconhecido (similaridade {score:.2f})",
                    notify=flag_config.notify,
                ))
        finally:
            session.close()

        return flags
