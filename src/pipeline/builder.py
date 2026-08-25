"""
builder.py

Assembles the "real" CameraPipeline (Detector + YOLO Tracker) from
TaskConfig and AppSettings. Cameras without any task assigned in
tasks.yaml produce no pipeline — there is nothing to infer.

All tasks of one camera share a single Detector (and therefore a single
YOLO model): the model is picked from the first TaskConfig that defines
"model", or from the default for the resolved device when none does.
"""

import logging

from config.schema import AppSettings, TaskConfig
from notify.flag_manager import FlagManager
from vision.detector import Detector
from vision.device import default_model_for_device, resolve_device
from vision.model_registry import ModelRegistry, default_registry
from vision.tracker import Tracker

from .camera_pipeline import CameraPipeline

logger = logging.getLogger("cv_central.pipeline.builder")


def _pick_model_path(task_configs: list[TaskConfig], device: str, app_settings: AppSettings) -> str:
    for task in task_configs:
        if task.model:
            return task.model
    return default_model_for_device(device, app_settings.vision.model_size_override)


def build_camera_pipeline(
    camera_id: str,
    task_configs: list[TaskConfig],
    flag_manager: FlagManager,
    app_settings: AppSettings,
    registry: ModelRegistry | None = None,
) -> CameraPipeline | None:
    if not task_configs:
        return None

    registry = registry or default_registry
    device = resolve_device(app_settings.vision.device)
    model_path = _pick_model_path(task_configs, device, app_settings)

    detector = Detector(model_path=model_path, device=device, registry=registry)
    tracker = Tracker()

    return CameraPipeline(
        camera_id,
        task_configs,
        flag_manager,
        detect_fn=detector.detect,
        track_fn=tracker.update,
    )


def build_pipelines(
    camera_ids: list[str],
    tasks_by_camera: dict[str, list[TaskConfig]],
    flag_manager: FlagManager,
    app_settings: AppSettings,
    registry: ModelRegistry | None = None,
) -> tuple[dict[str, CameraPipeline], dict[str, float]]:
    pipelines: dict[str, CameraPipeline] = {}
    fps_by_camera: dict[str, float] = {}

    for camera_id in camera_ids:
        task_configs = tasks_by_camera.get(camera_id, [])

        # A misconfigured task must not take down the whole
        # application: the common case is a task just added through an
        # interface, still WITHOUT calibrated geometry (item_counting
        # with no counting_line, for example), which makes the
        # TaskAnalyzer blow up while being constructed. Before this, the
        # error propagated up to startup and the application would not
        # even open — now only the affected camera goes without a
        # pipeline, and the reason lands in the log.
        try:
            pipeline = build_camera_pipeline(camera_id, task_configs, flag_manager, app_settings, registry)
        except Exception as error:
            logger.warning(
                "Camera '%s' has no pipeline: %s. "
                "Check that camera's tasks in tasks.yaml "
                "(tasks with a line/zone must be calibrated before they can run).",
                camera_id, error,
            )
            continue

        if pipeline is None:
            continue
        pipelines[camera_id] = pipeline
        fps_by_camera[camera_id] = max((t.detect_fps for t in task_configs), default=5.0)

    return pipelines, fps_by_camera
