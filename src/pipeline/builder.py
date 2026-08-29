"""
builder.py

Assembles the "real" CameraPipeline (per-task Detector + Tracker
engines) from TaskConfig and AppSettings. Cameras without any task
assigned in tasks.yaml produce no pipeline — there is nothing to infer.

Each task resolves to a (model_path, ModelKind) pair (tasks/model_kinds.py);
tasks that resolve to the SAME pair share one Detector+Tracker engine
(this is what keeps today's common case — no task sets an explicit
`model` — behaviorally identical to the old single-shared-detector
design). A task whose kind is ModelKind.NONE (self-managed inference,
e.g. face_id) gets no engine at all. A configured model whose actual
Ultralytics task doesn't match what the TaskAnalyzer declares raises
ValueError, which build_pipelines()'s per-camera try/except turns into
"this camera has no pipeline" rather than an app-wide crash.
"""

import logging

from config.schema import AppSettings, TaskConfig
from notify.flag_manager import FlagManager
from tasks.model_kinds import model_kind_for
from vision.detector import Detector
from vision.device import default_model_for_device, resolve_device
from vision.model_kind import ModelKind
from vision.model_registry import ModelRegistry, default_registry
from vision.results import ObbTrack, PoseTrack, SegmentationTrack
from vision.tracker import Tracker
from vision.types import Track

from .camera_pipeline import CameraPipeline

logger = logging.getLogger("cv_central.pipeline.builder")

_TRACK_CLS_BY_KIND = {
    ModelKind.DETECTION: Track,
    ModelKind.OBB: ObbTrack,
    ModelKind.SEGMENTATION: SegmentationTrack,
    ModelKind.POSE: PoseTrack,
}


def _resolve_model_spec(task: TaskConfig, device: str, app_settings: AppSettings):
    kind = model_kind_for(task)
    if kind is ModelKind.NONE:
        return None
    model_path = task.model or default_model_for_device(device, app_settings.vision.model_size_override)
    return model_path, kind


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

    engines: dict[tuple[str, ModelKind], tuple[Detector, Tracker]] = {}
    task_engine_key: dict[int, tuple[str, ModelKind] | None] = {}

    for index, task in enumerate(task_configs):
        spec = _resolve_model_spec(task, device, app_settings)
        task_engine_key[index] = spec
        if spec is None:
            continue

        model_path, kind = spec
        if spec in engines:
            continue

        actual_kind = registry.kind_of(model_path, device)
        if actual_kind != kind:
            raise ValueError(
                f"Task '{task.type}' requires a {kind.value} model but "
                f"'{model_path}' is a {actual_kind.value} model."
            )

        detector = Detector(model_path=model_path, device=device, registry=registry, kind=kind)
        tracker = Tracker(track_cls=_TRACK_CLS_BY_KIND.get(kind, Track))
        engines[spec] = (detector, tracker)

    return CameraPipeline(
        camera_id,
        task_configs,
        flag_manager,
        engines=engines,
        task_engine_key=task_engine_key,
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
