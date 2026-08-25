"""
builder.py

Monta CameraPipeline "de verdade" (Detector + Tracker YOLO) a partir de
TaskConfig e AppSettings. Câmeras sem nenhuma tarefa atribuída em
tasks.yaml não geram pipeline — nada a inferir.

Todas as tarefas de uma câmera compartilham um único Detector (e,
portanto, um único modelo YOLO): o modelo é escolhido a partir da
primeira TaskConfig que define "model", ou do padrão para o device
resolvido caso nenhuma defina.
"""

from config.schema import AppSettings, TaskConfig
from notify.flag_manager import FlagManager
from vision.detector import Detector
from vision.device import default_model_for_device, resolve_device
from vision.model_registry import ModelRegistry, default_registry
from vision.tracker import Tracker

from .camera_pipeline import CameraPipeline


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
        pipeline = build_camera_pipeline(camera_id, task_configs, flag_manager, app_settings, registry)
        if pipeline is None:
            continue
        pipelines[camera_id] = pipeline
        fps_by_camera[camera_id] = max((t.detect_fps for t in task_configs), default=5.0)

    return pipelines, fps_by_camera
