"""
tasks

Package of TaskAnalyzers. Importing this package registers every
built-in task (see registry.py) — whoever assembles the pipelines only
needs `import tasks` for the types to become usable in tasks.yaml.
"""

from . import missing_product, ppe_compliance, print_monitor, treadmill_counter  # noqa: F401

try:
    from . import face_id  # noqa: F401
except ImportError:
    pass  # insightface/onnxruntime not installed — face_id becomes
    # unavailable, the rest of the application keeps working normally.

try:
    from . import car_identification  # noqa: F401
except ImportError:
    pass  # easyocr not installed — car_identification becomes
    # unavailable, the rest of the application keeps working normally.
