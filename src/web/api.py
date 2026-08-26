"""
api.py

REST routes consumed by the JavaScript in static/js/. Every route is a
thin shell over the existing backend — no business logic lives here:

    cameras/video   camera/camera_manager.py + pipeline/results_store.py
    alerts          notify/flag_manager.py
    summary (AI)    llm/narrator.py
    tasks           config/writer.py (TasksYamlWriter)
    calibration     config/calibration.py
    employees       db/repository.py + vision/face/recognizer.py
    translations    i18n.py

Conventions:
  - Everything returns JSON, except /stream and /snapshot (images).
  - Errors are raised as ApiError (see errors.py), which answers with
    {"detail": "<english text>", "code": "<translation key>"} so the
    browser can show the message in the language the user picked.
  - Timestamps are epoch seconds (float), formatted in the browser.
"""

import logging
import os
import re
import threading
from urllib.parse import quote, unquote, urlparse

import cv2
import numpy as np
from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

import i18n
from bootstrap import AppRuntime
from config.calibration import CalibrationError, build_geometry_params, geometry_kind
from config.cameras_writer import CamerasYamlWriter
from config.schema import CameraConfig
from config.writer import TasksYamlWriter
from db import repository
from db.session import get_session
from security import env_vault
from tasks.registry import available_types

from . import streaming
from .deps import get_runtime, peek_runtime, set_runtime
from .errors import ApiError

logger = logging.getLogger("cv_central.web.api")

router = APIRouter(prefix="/api")

# Project root (two levels up from src/web/api.py) — where .env/.env.enc
# live, passed to security/env_vault.py's functions.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ---------------------------------------------------------------------- #
# Request models (Pydantic validates types and returns 422 on its own)
# ---------------------------------------------------------------------- #
class NewTaskPayload(BaseModel):
    type: str


class TaskUpdatePayload(BaseModel):
    """Absent fields (None) are left untouched — this allows saving just
    detect_fps without rewriting params, and vice versa."""
    detect_fps: float | None = Field(default=None, gt=0)
    params: dict | None = None


class FlagPayload(BaseModel):
    id: str
    enabled: bool = True
    severity: str = "info"
    notify: list[str] = Field(default_factory=list)


class FlagsUpdatePayload(BaseModel):
    flags: list[FlagPayload]


class GeometryPayload(BaseModel):
    """Points in pixels of the frame at NATIVE resolution — the
    front-end converts the <canvas> coordinates before sending."""
    points: list[tuple[float, float]]
    zone_name: str | None = None
    expected_class: str | None = None


class CameraCreatePayload(BaseModel):
    """Fields for the Live screen's "Add camera" panel. The connection
    string is assembled server-side from protocol/host/port/path/
    username/password — the browser never builds a raw URL."""
    id: str | None = None
    name: str = Field(min_length=1)
    protocol: str = "rtsp"  # rtsp | http | https
    host: str = Field(min_length=1)
    port: int | None = Field(default=None, gt=0, le=65535)
    path: str = ""
    username: str | None = None
    password: str | None = None
    enabled: bool = True


class CameraUpdatePayload(BaseModel):
    """Absent fields (None) are left untouched, same convention as
    TaskUpdatePayload — the per-camera settings panel only sends what
    changed."""
    name: str | None = None
    protocol: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, gt=0, le=65535)
    path: str | None = None
    username: str | None = None
    password: str | None = None
    enabled: bool | None = None


# ---------------------------------------------------------------------- #
# Translations
# ---------------------------------------------------------------------- #
@router.get("/i18n")
def get_i18n():
    """The full translation catalog, plus the languages available and
    the one configured in app.yaml.

    The browser fetches this once at startup and switches language
    locally — no reload and no round-trip per language change. The
    catalog lives in src/i18n.py and is shared with the desktop GUI, so
    there is only one place to edit wording.

    Deliberately does NOT require the vault to be unlocked (uses
    peek_runtime(), not get_runtime()) — the lock screen itself needs
    this to show translated text before AppRuntime even exists.
    """
    runtime = peek_runtime()
    default = i18n.normalize(runtime.app_settings.ui.language) if runtime else i18n.DEFAULT_LANGUAGE
    return {
        "languages": [{"code": code, "label": label} for code, label in i18n.LANGUAGES],
        "default": default,
        "catalog": {code: i18n.catalog_for(code) for code, _label in i18n.LANGUAGES},
    }


# ---------------------------------------------------------------------- #
# Credential vault (security/env_vault.py) — the browser's lock screen,
# and the "Exit application" button.
#
# The web app starts LOCKED (no AppRuntime at all) precisely so it can
# be launched by double-clicking run-html.sh, with no terminal to type
# a password into or to Ctrl+C: everything happens here instead.
# ---------------------------------------------------------------------- #
class UnlockPayload(BaseModel):
    password: str = Field(min_length=1)
    # Only checked on first run (no .env.enc yet), where the lock screen
    # asks the password twice to guard against a typo locking you out.
    confirm: str | None = None


def _enc_path() -> str:
    return os.path.join(PROJECT_ROOT, env_vault.ENC_FILENAME)


@router.get("/lock")
def get_lock_status():
    """Whether the vault is locked, and whether this is a first run (no
    .env.enc yet — the lock screen must ask the user to CHOOSE a
    password instead of entering an existing one). Polled once by the
    browser before anything else renders."""
    return {
        "unlocked": env_vault.is_unlocked(),
        "first_run": not os.path.exists(_enc_path()),
    }


@router.post("/unlock")
def unlock_vault(payload: UnlockPayload, request: Request):
    """Unlocks (or, on first run, creates) the encrypted credential
    store from the browser's lock screen, then builds and starts the
    real backend — the web equivalent of the terminal prompt in
    security/env_vault.py's unlock_interactive(), which the desktop GUI
    (src/main.py) still uses instead of this route."""
    if env_vault.is_unlocked():
        return {"ok": True}

    if os.path.exists(_enc_path()):
        try:
            env_vault.unlock_with_password(PROJECT_ROOT, payload.password)
        except env_vault.VaultError as error:
            remaining = env_vault.record_failed_attempt()
            if remaining <= 0:
                # Same brute-force guard the terminal flow had (it gave
                # up after MAX_ATTEMPTS and exited) — here that means
                # shutting the whole application down instead of just
                # rejecting the request.
                _trigger_shutdown(request)
                raise ApiError(423, "api.too_many_attempts") from error
            raise ApiError(401, "api.wrong_password", remaining=remaining) from error
        env_vault.reset_failed_attempts()
    else:
        if payload.confirm is not None and payload.confirm != payload.password:
            raise ApiError(400, "api.password_mismatch")
        env_vault.create_with_password(PROJECT_ROOT, payload.password)

    runtime = AppRuntime.create()
    if request.app.state.start_backend:
        runtime.start()
    set_runtime(runtime)

    return {"ok": True}


@router.post("/shutdown")
def shutdown_app(request: Request):
    """Gracefully stops the backend and terminates the process — the
    UI's "Exit application" button, for when the application was
    started by double-clicking run-html.sh and there is no terminal to
    Ctrl+C. Works whether the vault is locked or not."""
    _trigger_shutdown(request)
    return {"ok": True}


def _trigger_shutdown(request: Request) -> None:
    """Asks uvicorn to stop serving -- the SAME shutdown path as Ctrl+C
    (uvicorn's signal handler also just sets should_exit): the FastAPI
    lifespan's code after `yield` (web/server.py) still runs, stopping
    the camera/inference threads before the process exits.

    That graceful path is not guaranteed to be fast: a camera stuck
    mid-connect can block CameraStream.stop()'s thread join well past
    its own 2s timeout, because the block happens inside a native
    OpenCV/FFmpeg call that ignores it. So this also arms a hard
    fallback that force-exits a few seconds later if the process is
    still around by then -- the whole point of the "Exit application"
    button is to be a shutdown that actually works when a plain Ctrl+C
    (or killing the PID) would leave things in an inconsistent state.
    Safe either way: the vault's decrypted content only ever lives in
    memory (security/env_vault.py), so there is nothing on disk to lose
    by skipping the graceful path.

    Only arms when THIS app owns a real uvicorn Server (set by
    main_web.py) — without one there is nothing to shut down (tests,
    or create_web_app() embedded some other way), and unconditionally
    scheduling os._exit() would kill whatever hosting process this is
    running inside instead."""
    server = request.app.state.uvicorn_server
    if server is None:
        return

    server.should_exit = True

    timer = threading.Timer(5.0, lambda: os._exit(0))
    timer.daemon = True
    timer.start()


# ---------------------------------------------------------------------- #
# General state — the single endpoint the dashboard polls
# ---------------------------------------------------------------------- #
@router.get("/state")
def get_state(alert_limit: int = 100, runtime=Depends(get_runtime)):
    """Everything the UI refreshes periodically, in one request: camera
    status, recent alerts and the narrator summary.

    One aggregated endpoint (instead of three) keeps the front-end
    polling simple and avoids screens showing information from
    different instants."""
    return {
        "cameras": [_camera_state(runtime, camera_id, name)
                    for camera_id, name in runtime.camera_manager.list_cameras()],
        "alerts": [_flag_to_dict(flag) for flag in runtime.flag_manager.recent(limit=alert_limit)],
        "summary": runtime.latest_summary(),
        "narrator_enabled": runtime.narrator is not None,
    }


def _camera_state(runtime, camera_id: str, name: str) -> dict:
    result = runtime.results_store.get(camera_id)
    tracks = result[1] if result is not None else []

    # How many objects of each class are being tracked right now — this
    # becomes the summary ("3 person, 1 bottle") in each card's footer.
    class_counts: dict[str, int] = {}
    for track in tracks:
        class_counts[track.class_name] = class_counts.get(track.class_name, 0) + 1

    return {
        "id": camera_id,
        "name": name,
        "host": _hostname_of(getattr(runtime.camera_manager.cameras.get(camera_id), "url", None)),
        "connected": runtime.camera_manager.is_connected(camera_id),
        "has_pipeline": camera_id in runtime.engine.pipelines,
        "track_count": len(tracks),
        "class_counts": class_counts,
    }


def _hostname_of(url: str | None) -> str | None:
    """IPv4/hostname of a camera's URL, with no credentials — safe to
    send to the browser. Used to hyperlink the camera's own web
    configuration page (http://<host>) from the Live screen."""
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def _flag_to_dict(flag) -> dict:
    """`message` is the rendered English text; `message_key`/
    `message_params` are the translatable form of the same message, so
    the browser can show it in the chosen language (see i18n.py)."""
    return {
        "camera_id": flag.camera_id,
        "task_type": flag.task_type,
        "flag_id": flag.flag_id,
        "severity": flag.severity,
        "message": flag.message,
        "message_key": getattr(flag, "message_key", ""),
        "message_params": getattr(flag, "message_params", {}),
        "notify": list(flag.notify or []),
        "timestamp": flag.timestamp,
    }


@router.get("/system")
def get_system(runtime=Depends(get_runtime)):
    """Static information shown in the sidebar footer: inference device,
    active notification channels, LLM status."""
    from vision.device import resolve_device

    settings = runtime.app_settings
    return {
        "device": resolve_device(settings.vision.device),
        "device_setting": settings.vision.device,
        "model_override": settings.vision.model_size_override,
        "db_enabled": settings.db.enabled,
        "db_url": settings.db.url,
        "llm_enabled": settings.llm.enabled,
        "llm_model": settings.llm.model,
        "desktop_notifications": settings.notify.desktop_enabled,
        "notify_channels": sorted(runtime.flag_manager.notifiers.keys()),
        "camera_count": len(runtime.camera_manager.list_cameras()),
        "pipeline_count": len(runtime.engine.pipelines),
        "tasks_yaml_path": runtime.tasks_yaml_path,
        "cameras_yaml_path": runtime.cameras_yaml_path,
        "language": i18n.normalize(settings.ui.language),
    }


# ---------------------------------------------------------------------- #
# Video
# ---------------------------------------------------------------------- #
@router.get("/cameras/{camera_id}/stream")
def get_stream(
    camera_id: str,
    width: int = Query(default=streaming.DEFAULT_MAX_WIDTH, ge=0, le=3840),
    quality: int = Query(default=streaming.DEFAULT_QUALITY, ge=1, le=100),
    fps: float = Query(default=streaming.DEFAULT_FPS, gt=0, le=60),
    overlay: bool = True,
    runtime=Depends(get_runtime),
):
    """Live MJPEG video, consumed by an <img> in the UI.

    `overlay=false` delivers the raw video, without detection boxes —
    that is the "Detection boxes" switch in the toolbar.

    The connection stays open until the browser closes it (switching
    tabs, reloading the page). Each open <img> is one connection."""
    _require_camera(runtime, camera_id)

    return StreamingResponse(
        streaming.mjpeg_stream(runtime, camera_id, max_width=width, quality=quality,
                               fps=fps, overlay=overlay),
        media_type=f"multipart/x-mixed-replace; boundary={streaming.BOUNDARY}",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


@router.get("/cameras/{camera_id}/snapshot")
def get_snapshot(
    camera_id: str,
    overlay: bool = False,
    width: int = Query(default=0, ge=0, le=3840),
    quality: int = Query(default=90, ge=1, le=100),
    runtime=Depends(get_runtime),
):
    """A single JPEG frame.

    The calibration screen uses `width=0` (native resolution) and
    `overlay=false`: it needs the raw image so the clicked points map
    onto the pixels stored in tasks.yaml."""
    _require_camera(runtime, camera_id)

    if runtime.camera_manager.get_frame(camera_id) is None:
        raise ApiError(503, "api.no_frame")

    frame = streaming.render_frame(runtime, camera_id, overlay=overlay, max_width=width)
    jpeg = streaming.encode_jpeg(frame, quality)
    if jpeg is None:
        raise ApiError(500, "api.jpeg_failed")

    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


def _require_camera(runtime, camera_id: str) -> None:
    if camera_id not in runtime.camera_manager.cameras:
        raise ApiError(404, "api.camera_not_found")


# ---------------------------------------------------------------------- #
# Camera registry (config/cameras.yaml + the encrypted .env vault)
#
# The camera's connection string never touches cameras.yaml directly:
# the yaml only stores an "${VAR}" reference (_ENV_REF below), and the
# actual host/port/path/credentials live in the vault (security/
# env_vault.py), the same one .env was encrypted into at startup. This
# mirrors the hand-written convention already used by CAM1_URL/CAM2_URL.
# ---------------------------------------------------------------------- #
_ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _env_var_of(entry) -> str | None:
    match = _ENV_REF.match(entry.get("url", "") or "")
    return match.group(1) if match else None


def _env_var_for(camera_id: str) -> str:
    return f"CAM_{re.sub(r'[^A-Z0-9]+', '_', camera_id.upper()).strip('_')}_URL"


def _resolve_camera_url(entry) -> str:
    """The camera's real connection string: from the vault when the yaml
    references one (the normal case), the raw value otherwise (a
    literal URL typed by hand), falling back to a plain environment
    variable so this also works when the vault was never unlocked (e.g.
    the web app created directly, as the test suite does)."""
    var = _env_var_of(entry)
    if var is None:
        return entry.get("url", "") or ""
    return env_vault.get(var) or os.environ.get(var, "")


def _build_camera_url(protocol: str, host: str, port: int | None, path: str,
                       username: str | None, password: str | None) -> str:
    auth = ""
    if username:
        auth = quote(username, safe="")
        if password:
            auth += f":{quote(password, safe='')}"
        auth += "@"

    netloc = f"{auth}{host}"
    if port:
        netloc += f":{port}"

    path = path or ""
    if path and not path.startswith("/") and not path.startswith("?"):
        path = "/" + path

    return f"{protocol}://{netloc}{path}"


def _split_camera_url(url: str) -> dict:
    parsed = urlparse(url)
    return {
        "protocol": parsed.scheme or "rtsp",
        "host": parsed.hostname or "",
        "port": parsed.port,
        "path": (parsed.path or "") + (f"?{parsed.query}" if parsed.query else ""),
        "username": unquote(parsed.username) if parsed.username else "",
        "password": unquote(parsed.password) if parsed.password else "",
    }


def _camera_detail(entry, include_secret: bool = False) -> dict:
    url = _resolve_camera_url(entry)
    parts = _split_camera_url(url) if url else {}
    detail = {
        "id": entry.get("id"),
        "name": entry.get("name", entry.get("id")),
        "enabled": bool(entry.get("enabled", True)),
        "protocol": parts.get("protocol", "rtsp"),
        "host": parts.get("host", ""),
        "port": parts.get("port"),
        "path": parts.get("path", ""),
        "username": parts.get("username", ""),
    }
    if include_secret:
        detail["password"] = parts.get("password", "")
    return detail


def _vault_set(env_var: str, url: str) -> None:
    try:
        env_vault.set_value(env_var, url)
    except env_vault.VaultError as error:
        raise ApiError(500, "api.vault_locked") from error


def _vault_delete(env_var: str) -> None:
    try:
        env_vault.delete_value(env_var)
    except env_vault.VaultError as error:
        raise ApiError(500, "api.vault_locked") from error


def _slugify_id(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "camera"
    candidate = base
    suffix = 2
    while candidate in taken:
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


@router.get("/cameras")
def list_cameras(runtime=Depends(get_runtime)):
    """Camera registry (connection details, no password) — backs the
    Live screen's "Add camera" panel and hyperlinked host."""
    writer = CamerasYamlWriter(runtime.cameras_yaml_path)
    return [_camera_detail(entry) for entry in writer.list_entries()]


@router.get("/cameras/{camera_id}")
def get_camera(camera_id: str, runtime=Depends(get_runtime)):
    """Full connection details of ONE camera, including its password —
    only requested when the per-camera settings panel (the cog button)
    is opened, never as part of the general camera list."""
    writer = CamerasYamlWriter(runtime.cameras_yaml_path)
    entry = writer.find(camera_id)
    if entry is None:
        raise ApiError(404, "api.camera_not_found")
    return _camera_detail(entry, include_secret=True)


@router.post("/cameras", status_code=201)
def create_camera(payload: CameraCreatePayload, runtime=Depends(get_runtime)):
    writer = CamerasYamlWriter(runtime.cameras_yaml_path)
    taken = {entry.get("id") for entry in writer.list_entries()}

    camera_id = (payload.id or "").strip() or _slugify_id(payload.name, taken)
    if camera_id in taken:
        raise ApiError(409, "api.camera_already_exists")

    url = _build_camera_url(payload.protocol, payload.host, payload.port, payload.path,
                             payload.username, payload.password)
    env_var = _env_var_for(camera_id)
    _vault_set(env_var, url)
    writer.add(camera_id, payload.name.strip(), f"${{{env_var}}}", payload.enabled)

    if payload.enabled:
        runtime.add_camera(CameraConfig(id=camera_id, name=payload.name.strip(), url=url, enabled=True))

    return _camera_detail(writer.find(camera_id))


@router.patch("/cameras/{camera_id}")
def update_camera(camera_id: str, payload: CameraUpdatePayload, runtime=Depends(get_runtime)):
    writer = CamerasYamlWriter(runtime.cameras_yaml_path)
    entry = writer.find(camera_id)
    if entry is None:
        raise ApiError(404, "api.camera_not_found")

    current = _split_camera_url(_resolve_camera_url(entry))
    new_name = payload.name.strip() if payload.name is not None else entry.get("name", camera_id)
    new_url = _build_camera_url(
        protocol=payload.protocol or current.get("protocol", "rtsp"),
        host=payload.host if payload.host is not None else current.get("host", ""),
        port=payload.port if payload.port is not None else current.get("port"),
        path=payload.path if payload.path is not None else current.get("path", ""),
        username=payload.username if payload.username is not None else current.get("username", ""),
        password=payload.password if payload.password is not None else current.get("password", ""),
    )

    env_var = _env_var_of(entry) or _env_var_for(camera_id)
    _vault_set(env_var, new_url)

    new_enabled = payload.enabled if payload.enabled is not None else bool(entry.get("enabled", True))
    writer.update(camera_id, name=new_name, url_ref=f"${{{env_var}}}", enabled=new_enabled)

    config = CameraConfig(id=camera_id, name=new_name, url=new_url, enabled=new_enabled)
    if new_enabled:
        runtime.update_camera(config)
    else:
        runtime.remove_camera(camera_id)

    return _camera_detail(writer.find(camera_id))


@router.delete("/cameras/{camera_id}")
def delete_camera(camera_id: str, runtime=Depends(get_runtime)):
    writer = CamerasYamlWriter(runtime.cameras_yaml_path)
    entry = writer.find(camera_id)
    if entry is None:
        raise ApiError(404, "api.camera_not_found")

    env_var = _env_var_of(entry)
    writer.remove(camera_id)
    runtime.remove_camera(camera_id)
    if env_var:
        _vault_delete(env_var)

    return {"ok": True}


# ---------------------------------------------------------------------- #
# Tasks (config/tasks.yaml)
# ---------------------------------------------------------------------- #
@router.get("/task-types")
def get_task_types():
    """Types registered in tasks/registry.py — populates the "new task"
    select. It includes each type's geometry kind, so the calibration
    screen knows whether to draw a line, a polygon or nothing."""
    return [
        {"type": task_type, "geometry": geometry_kind(task_type)}
        for task_type in available_types()
    ]


@router.get("/cameras/{camera_id}/tasks")
def get_tasks(camera_id: str, runtime=Depends(get_runtime)):
    """Tasks of the camera, read from tasks.yaml on every call (rather
    than from a cache) — this way the UI reflects edits made to the file
    by hand."""
    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    return [_task_to_dict(index, task) for index, task in enumerate(writer.get_tasks(camera_id))]


def _task_to_dict(index: int, task) -> dict:
    task_type = task.get("type", "")
    params = _plain(task.get("params", {}) or {})

    return {
        "index": index,
        "type": task_type,
        "model": task.get("model"),
        "detect_fps": float(task.get("detect_fps", 5.0)),
        "params": params,
        "geometry": geometry_kind(task_type),
        "flags": [
            {
                "id": flag.get("id", ""),
                "enabled": bool(flag.get("enabled", True)),
                "severity": flag.get("severity", "info"),
                "notify": list(flag.get("notify", []) or []),
            }
            for flag in (task.get("flags", []) or [])
        ],
    }


def _plain(value):
    """Converts ruamel.yaml structures (CommentedMap/CommentedSeq) into
    plain dicts/lists — FastAPI's JSON serializer does not know how to
    handle the commented types."""
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return value


@router.post("/cameras/{camera_id}/tasks", status_code=201)
def add_task(camera_id: str, payload: NewTaskPayload, runtime=Depends(get_runtime)):
    if payload.type not in available_types():
        raise ApiError(400, "api.unknown_task_type")

    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    writer.add_task(camera_id, payload.type)
    return {"ok": True, "type": payload.type}


@router.patch("/cameras/{camera_id}/tasks/{task_index}")
def update_task(camera_id: str, task_index: int, payload: TaskUpdatePayload, runtime=Depends(get_runtime)):
    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    _require_task(writer, camera_id, task_index)

    if payload.detect_fps is not None:
        writer.set_task_detect_fps(camera_id, task_index, payload.detect_fps)
    if payload.params is not None:
        writer.set_task_params(camera_id, task_index, payload.params)

    return {"ok": True}


@router.delete("/cameras/{camera_id}/tasks/{task_index}")
def delete_task(camera_id: str, task_index: int, runtime=Depends(get_runtime)):
    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    _require_task(writer, camera_id, task_index)

    writer.remove_task(camera_id, task_index)
    return {"ok": True}


@router.put("/cameras/{camera_id}/tasks/{task_index}/flags")
def update_flags(camera_id: str, task_index: int, payload: FlagsUpdatePayload, runtime=Depends(get_runtime)):
    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    _require_task(writer, camera_id, task_index)

    for flag in payload.flags:
        writer.set_flag(
            camera_id, task_index, flag.id,
            enabled=flag.enabled, severity=flag.severity, notify=flag.notify,
        )
    return {"ok": True}


@router.post("/cameras/{camera_id}/tasks/{task_index}/geometry")
def save_geometry(camera_id: str, task_index: int, payload: GeometryPayload, runtime=Depends(get_runtime)):
    """Saves the line/zone drawn on the calibration screen. Validation
    is the same as the Qt GUI's (config/calibration.py)."""
    writer = TasksYamlWriter(runtime.tasks_yaml_path)
    task = _require_task(writer, camera_id, task_index)

    try:
        params = build_geometry_params(
            task.get("type"),
            _plain(task.get("params", {}) or {}),
            [tuple(point) for point in payload.points],
            zone_name=payload.zone_name,
            expected_class=payload.expected_class,
        )
    except CalibrationError as error:
        # The exception already carries a translation code, so the
        # browser shows this in the language the user picked.
        raise ApiError(400, error.code) from error

    writer.set_task_params(camera_id, task_index, params)
    return {"ok": True, "params": _plain(params)}


def _require_task(writer: TasksYamlWriter, camera_id: str, task_index: int):
    tasks = writer.get_tasks(camera_id)
    if task_index < 0 or task_index >= len(tasks):
        raise ApiError(404, "api.task_not_found")
    return tasks[task_index]


@router.post("/reload")
def reload_pipelines(runtime=Depends(get_runtime)):
    """Rebuilds the inference pipelines from the current tasks.yaml,
    without restarting the application.

    Without this, editing tasks through the UI would only take effect on
    the next run (that is the Qt GUI's behavior, which only writes the
    YAML). The already-loaded YOLO weights are reused through the
    ModelRegistry, so the rebuild is fast."""
    count = runtime.reload_tasks()
    return {"ok": True, "pipeline_count": count}


# ---------------------------------------------------------------------- #
# Employees (face recognition)
# ---------------------------------------------------------------------- #
@router.get("/employees")
def list_employees():
    session = get_session()
    try:
        return [
            {"id": employee.id, "name": employee.name, "created_at": employee.created_at,
             "embedding_count": len(employee.embeddings)}
            for employee in repository.list_employees(session)
        ]
    finally:
        session.close()


@router.post("/employees", status_code=201)
async def enroll_employee(
    name: str = Form(...),
    camera_id: str | None = Form(default=None),
    photo: UploadFile | None = File(default=None),
    runtime=Depends(get_runtime),
):
    """Enrolls an employee from a photo uploaded by the browser OR from
    the current frame of a camera.

    Mirrors gui_qt/widgets/employee_enrollment.py: extracts the face
    embedding with InsightFace and stores employee + vector in the
    database."""
    name = name.strip()
    if not name:
        raise ApiError(400, "api.employee_name_required")

    frame = await _resolve_enrollment_frame(runtime, camera_id, photo)
    face = _extract_best_face(frame)

    session = get_session()
    try:
        employee = repository.add_employee(session, name)
        repository.add_face_embedding(session, employee.id, face.embedding)
        return {"ok": True, "id": employee.id, "name": employee.name,
                "det_score": float(face.det_score)}
    finally:
        session.close()


async def _resolve_enrollment_frame(runtime, camera_id: str | None, photo: UploadFile | None):
    """Source frame for the enrollment: the upload takes precedence over
    the camera capture if both arrive."""
    if photo is not None and photo.filename:
        raw = await photo.read()
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise ApiError(400, "api.image_unreadable")
        return frame

    if camera_id:
        _require_camera(runtime, camera_id)
        frame = runtime.camera_manager.get_frame(camera_id)
        if frame is None:
            raise ApiError(503, "api.no_frame")
        return frame

    raise ApiError(400, "api.photo_or_camera_required")


def _extract_best_face(frame):
    """Face with the highest detection score in the frame. The
    recognizer import is deferred because insightface/onnxruntime are
    optional — without them the rest of the application keeps
    working."""
    try:
        from vision.device import default_face_model_for_device, resolve_device
        from vision.face.recognizer import get_face_recognizer
    except ImportError as error:
        raise ApiError(501, "api.face_unavailable") from error

    runtime = get_runtime()
    device = resolve_device(runtime.app_settings.vision.device)
    recognizer = get_face_recognizer(default_face_model_for_device(device))

    faces = recognizer.analyze(frame)
    if not faces:
        raise ApiError(400, "api.face_not_detected")
    return max(faces, key=lambda face: face.det_score)
