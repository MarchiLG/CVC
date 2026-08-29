"""
plate_reader.py

License plate OCR via EasyOCR — kept in its own module, separate from
vision/car_id.py's classifier/color helpers, so importing THIS is the
only place car_identification's optional easyocr dependency is
actually required (see tasks/__init__.py's try/except guard around
`from . import car_identification`).
"""

import threading

import easyocr


class PlateReader:
    def __init__(self, languages: tuple[str, ...] = ("en",), min_confidence: float = 0.4):
        self._reader = easyocr.Reader(list(languages))
        self.min_confidence = min_confidence

    def read(self, crop) -> str:
        """Best-guess plate text, "" if the crop is empty or nothing was
        read with enough confidence."""
        if crop is None or crop.size == 0:
            return ""
        results = self._reader.readtext(crop)
        candidates = [(text, confidence) for _bbox, text, confidence in results if confidence >= self.min_confidence]
        if not candidates:
            return ""
        text, _confidence = max(candidates, key=lambda item: item[1])
        return text.strip().upper()


_reader_lock = threading.Lock()
_reader_cache: dict[tuple[str, ...], PlateReader] = {}


def get_plate_reader(languages: tuple[str, ...] = ("en",)) -> PlateReader:
    with _reader_lock:
        reader = _reader_cache.get(languages)
        if reader is None:
            reader = PlateReader(languages)
            _reader_cache[languages] = reader
        return reader
