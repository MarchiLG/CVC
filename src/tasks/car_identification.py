"""
car_identification.py

For each tracked car (from the camera's shared DETECTION model — same
`tracks` argument item_counting reads), crops its bbox and runs two
self-managed secondary steps on the crop, independently of the
orchestrated per-camera model set (the same "call a model directly
inside analyze()" pattern face_id already uses for InsightFace):

    1. trademark/make — a genuine classification-kind model.
    2. color           — NOT a model: dominant-color extraction (see
                         vision/car_id.py's docstring for why).
    3. plate_text      — OCR (EasyOCR) over the crop.

Emits one Flag per identified car, `message_params["fields"]` carrying
the ordered [trademark, color, plate_text] array.

params expected in tasks.yaml:
    car_class: str (defaults to "car")           # tracked class name that counts as a car
    trademark_model: str (required)                # path under models/classification/
    ocr_languages: [str] (defaults to ["en"])
    min_confidence: float (defaults to 0.5)         # gate on the car detection's own confidence
    cooldown_seconds: float (defaults to 30.0)      # per track_id, so a car isn't re-run every frame
    device: "auto" | "cpu" | "cuda" (defaults to "auto")
"""

import time

from notify.flag import Flag
from vision.car_id import dominant_color, get_trademark_classifier
from vision.device import resolve_device
from vision.plate_reader import get_plate_reader

from .base import TaskAnalyzer
from .geometry import crop_bbox
from .registry import register

_DEFAULT_COOLDOWN_SECONDS = 30.0
_DEFAULT_MIN_CONFIDENCE = 0.5


@register("car_identification")
class CarIdentificationAnalyzer(TaskAnalyzer):
    type = "car_identification"

    def __init__(self, camera_id, config):
        super().__init__(camera_id, config)
        self.car_class = config.params.get("car_class", "car")
        self.min_confidence = config.params.get("min_confidence", _DEFAULT_MIN_CONFIDENCE)
        self.cooldown_seconds = config.params.get("cooldown_seconds", _DEFAULT_COOLDOWN_SECONDS)

        trademark_model = config.params["trademark_model"]
        device = resolve_device(config.params.get("device", "auto"))
        ocr_languages = tuple(config.params.get("ocr_languages", ["en"]))

        self._classifier = get_trademark_classifier(trademark_model, device)
        self._plate_reader = get_plate_reader(ocr_languages)
        self._last_identified: dict[int, float] = {}

    def analyze(self, frame, detections, tracks):
        flag_config = self.flag_config("car_identified")
        if flag_config is None or not flag_config.enabled:
            return []

        now = time.time()
        flags: list[Flag] = []

        for track in tracks:
            if track.class_name != self.car_class or track.confidence < self.min_confidence:
                continue
            if now - self._last_identified.get(track.track_id, 0.0) < self.cooldown_seconds:
                continue

            crop = crop_bbox(frame, track.bbox)
            if crop.size == 0:
                continue

            self._last_identified[track.track_id] = now

            trademark, _confidence = self._classifier.classify(crop)
            color = dominant_color(crop)
            plate_text = self._plate_reader.read(crop)
            fields = [trademark, color, plate_text]

            flags.append(Flag(
                camera_id=self.camera_id,
                task_type=self.type,
                flag_id="car_identified",
                severity=flag_config.severity,
                notify=flag_config.notify,
                message=f"Car #{track.track_id}: {trademark or '?'} / {color or '?'} / {plate_text or '?'}",
                message_key="flag.car_identified",
                # `fields` carries the literal ordered [trademark, color,
                # plate_text] array; the flattened keys alongside it are
                # what "flag.car_identified"'s {name} placeholders actually
                # use — the JS translator (web/static/js/i18n.js) only
                # matches \w+ placeholder names, not the `fields[0]`
                # subscript syntax Python's str.format would also accept.
                message_params={
                    "track_id": track.track_id,
                    "fields": fields,
                    "trademark": trademark or "?",
                    "color": color or "?",
                    "plate_text": plate_text or "?",
                },
            ))

        return flags
