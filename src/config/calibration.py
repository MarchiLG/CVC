"""
calibration.py

Geometry calibration rules: turns a list of points clicked over a frame
into the corresponding `params` block of a task in tasks.yaml (counting
line or zone polygon), validating what each task type requires.

It lives here, outside the interfaces, because BOTH UIs calibrate:

    gui_qt/widgets/calibration_view.py   draws on a QGraphicsScene and
                                         shows errors in a QMessageBox
    web/api.py                           receives the points from the
                                         <canvas> and returns errors as
                                         HTTP 400

Both call build_geometry_params() and differ only in HOW they present
the error message — the validation itself exists once.

Coordinates are always in pixels of the frame at its NATIVE resolution
(the same system used by counting_line/zones in tasks.yaml), never in
screen pixels: each UI is responsible for converting clicks back to the
native scale before calling in here.
"""

# Task types calibrated with a LINE (exactly 2 points).
LINE_TYPES = {"item_counting"}

# Task types calibrated with a ZONE (polygon, at least 3 points).
ZONE_TYPES = {"ppe_compliance", "missing_product"}


class CalibrationError(ValueError):
    """Invalid geometry for the task type.

    `code` is a stable identifier the interfaces translate for display
    (see web/static/js/i18n.js); the message carried by the exception is
    the English fallback, used by the desktop GUI and the logs.
    """

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def supports_geometry(task_type: str) -> bool:
    """Visual calibration only makes sense for tasks with geometry —
    `face_id`, for instance, has neither a line nor a zone."""
    return task_type in LINE_TYPES or task_type in ZONE_TYPES


def geometry_kind(task_type: str) -> str | None:
    """"line", "zone" or None — used by the UIs to pick the drawing mode
    (2 clicks vs. free polygon)."""
    if task_type in LINE_TYPES:
        return "line"
    if task_type in ZONE_TYPES:
        return "zone"
    return None


def build_geometry_params(
    task_type: str,
    existing_params: dict | None,
    points: list[tuple[float, float]],
    zone_name: str | None = None,
    expected_class: str | None = None,
) -> dict:
    """Returns a new `params` dict with the geometry applied.

    Nothing is written to disk — the caller passes the result to
    TasksYamlWriter.set_task_params(). Existing params are preserved
    (only the geometry keys are replaced).

    Raises CalibrationError if the geometry does not meet what the task
    type requires.
    """
    params = dict(existing_params or {})

    if task_type in LINE_TYPES:
        return _apply_counting_line(params, points)

    if task_type in ZONE_TYPES:
        return _apply_zone(params, task_type, points, zone_name, expected_class)

    raise CalibrationError(
        "calibration.unsupported_type",
        f"Visual calibration is not supported for '{task_type}'.",
    )


def _apply_counting_line(params: dict, points) -> dict:
    if len(points) != 2:
        raise CalibrationError(
            "calibration.line_needs_two_points",
            "Mark exactly 2 points for the counting line.",
        )

    (x1, y1), (x2, y2) = points
    params["counting_line"] = {
        "p1": [round(x1), round(y1)],
        "p2": [round(x2), round(y2)],
    }
    return params


def _apply_zone(params: dict, task_type: str, points, zone_name, expected_class) -> dict:
    if len(points) < 3:
        raise CalibrationError(
            "calibration.zone_needs_three_points",
            "Mark at least 3 points for the zone.",
        )

    name = (zone_name or "").strip()
    if not name:
        raise CalibrationError(
            "calibration.zone_name_required",
            "Enter a name for the zone.",
        )

    zone = {"name": name, "polygon": [[round(x), round(y)] for x, y in points]}

    if task_type == "missing_product":
        expected = (expected_class or "").strip()
        if not expected:
            raise CalibrationError(
                "calibration.expected_class_required",
                "Enter the expected class for the zone.",
            )
        zone["expected_class"] = expected

    # A zone with the same name is replaced (recalibrating does not
    # duplicate); a new name is appended to the list.
    zones = list(params.get("zones", []) or [])
    for index, existing in enumerate(zones):
        if existing.get("name") == name:
            zones[index] = zone
            break
    else:
        zones.append(zone)

    params["zones"] = zones
    return params
