"""
Tests for the web API (src/web/api.py).

They follow the same pattern as the Qt GUI tests: a fake
CameraManager/runtime in place of the real backend, so nothing here
opens a camera, loads YOLO or depends on the network. The routes are
exercised through FastAPI's TestClient, which speaks real HTTP to the
in-memory app.
"""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from notify.flag import Flag
from vision.types import Track
from web.server import create_web_app

TASKS_YAML = """\
cameras:
  cam1:
    tasks:
      - type: item_counting
        detect_fps: 5
        params: {}
        flags:
          - id: count_threshold
            enabled: true
            severity: warning
            notify: [log]
      - type: missing_product
        detect_fps: 3
        params:
          zones: []
        flags:
          - id: missing_product
            enabled: true
            severity: warning
            notify: [log, desktop]
"""


# ---------------------------------------------------------------------- #
# Backend doubles
# ---------------------------------------------------------------------- #
class _FakeCameraStream:
    def __init__(self, camera_id, name):
        self.camera_id = camera_id
        self.name = name


class _FakeCameraManager:
    def __init__(self, cameras, frames=None, connected=None):
        self._cameras = cameras
        self._frames = frames or {}
        self._connected = connected or {}
        self.cameras = {camera_id: _FakeCameraStream(camera_id, name) for camera_id, name in cameras}

    def list_cameras(self):
        return self._cameras

    def get_frame(self, camera_id):
        return self._frames.get(camera_id)

    def is_connected(self, camera_id):
        return self._connected.get(camera_id, False)

    def start_all(self):
        pass

    def stop_all(self):
        pass


class _FakeResultsStore:
    def __init__(self, results=None):
        self._results = results or {}

    def get(self, camera_id):
        return self._results.get(camera_id)


class _FakeFlagManager:
    def __init__(self, flags=None):
        self._flags = flags or []
        self.notifiers = {"log": object()}

    def recent(self, limit=50):
        return self._flags[-limit:]


class _FakeEngine:
    def __init__(self, pipelines=None):
        self.pipelines = pipelines or {}


class _FakeRuntime:
    """The same surface bootstrap.AppRuntime exposes to the UIs."""

    def __init__(self, tasks_yaml_path, cameras=None, frames=None, connected=None,
                 flags=None, results=None, pipelines=None):
        from config.schema import AppSettings

        self.camera_manager = _FakeCameraManager(cameras or [("cam1", "C1")], frames, connected)
        self.results_store = _FakeResultsStore(results)
        self.flag_manager = _FakeFlagManager(flags)
        self.engine = _FakeEngine(pipelines)
        self.app_settings = AppSettings()
        self.tasks_yaml_path = str(tasks_yaml_path)
        self.cameras_yaml_path = "cameras.yaml"
        self.narrator = None
        self.reload_count = 0

    def latest_summary(self):
        return None

    def reload_tasks(self):
        self.reload_count += 1
        return len(self.engine.pipelines)


@pytest.fixture
def tasks_path(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text(TASKS_YAML)
    return path


@pytest.fixture
def runtime(tasks_path):
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    track = Track(class_name="person", confidence=0.9, bbox=(10, 10, 50, 50), track_id=1)
    return _FakeRuntime(
        tasks_path,
        frames={"cam1": frame},
        connected={"cam1": True},
        results={"cam1": ([], [track])},
        pipelines={"cam1": object()},
    )


@pytest.fixture
def client(runtime):
    # start_backend=False: no capture/inference thread is started.
    return TestClient(create_web_app(runtime=runtime, start_backend=False))


# ---------------------------------------------------------------------- #
# Translations
# ---------------------------------------------------------------------- #
def test_i18n_serves_both_languages_with_english_default(client):
    body = client.get("/api/i18n").json()

    assert [entry["code"] for entry in body["languages"]] == ["en", "pt"]
    assert body["default"] == "en"
    assert set(body["catalog"]) == {"en", "pt"}
    assert body["catalog"]["en"]["nav.live"] == "Live"
    assert body["catalog"]["pt"]["nav.live"] == "Ao vivo"


def test_i18n_default_follows_app_yaml(tasks_path):
    """app.yaml -> ui.language sets the language the browser starts in
    (a picker choice already saved in that browser still wins)."""
    from config.schema import AppSettings, UiSettings

    runtime = _FakeRuntime(tasks_path)
    runtime.app_settings = AppSettings(ui=UiSettings(language="pt"))
    client = TestClient(create_web_app(runtime=runtime, start_backend=False))

    assert client.get("/api/i18n").json()["default"] == "pt"


# ---------------------------------------------------------------------- #
# General state
# ---------------------------------------------------------------------- #
def test_index_serves_the_html_ui(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Computer Vision Central" in response.text


def test_state_reports_camera_status_and_tracks(client):
    body = client.get("/api/state").json()

    camera = body["cameras"][0]
    assert camera["id"] == "cam1"
    assert camera["connected"] is True
    assert camera["has_pipeline"] is True
    assert camera["track_count"] == 1
    assert camera["class_counts"] == {"person": 1}


def test_state_exposes_translatable_alert_messages(tasks_path):
    """Analyzers send message_key + message_params so the browser can
    render the alert in the chosen language; `message` is the English
    fallback for flags built without a key."""
    flags = [Flag(camera_id="cam1", task_type="ppe_compliance", flag_id="missing_ppe",
                  severity="critical", message="Person #4 missing: helmet",
                  message_key="flag.missing_ppe",
                  message_params={"track_id": 4, "items": "helmet"},
                  timestamp=100.0)]
    client = TestClient(create_web_app(runtime=_FakeRuntime(tasks_path, flags=flags),
                                       start_backend=False))

    alert = client.get("/api/state").json()["alerts"][0]

    assert alert["message_key"] == "flag.missing_ppe"
    assert alert["message_params"] == {"track_id": 4, "items": "helmet"}
    assert alert["message"] == "Person #4 missing: helmet"


def test_state_includes_recent_flags(tasks_path):
    flags = [
        Flag(camera_id="cam1", task_type="item_counting", flag_id="count_threshold",
             severity="warning", message="first", timestamp=100.0),
        Flag(camera_id="cam1", task_type="missing_product", flag_id="missing_product",
             severity="critical", message="second", timestamp=200.0),
    ]
    client = TestClient(create_web_app(runtime=_FakeRuntime(tasks_path, flags=flags),
                                       start_backend=False))

    alerts = client.get("/api/state").json()["alerts"]

    # Chronological order: the front-end reverses it for display.
    assert [alert["message"] for alert in alerts] == ["first", "second"]
    assert alerts[1]["severity"] == "critical"


def test_system_reports_device_and_channels(client):
    body = client.get("/api/system").json()

    assert body["device"] in {"cpu", "cuda"}
    assert body["camera_count"] == 1
    assert body["pipeline_count"] == 1
    assert "log" in body["notify_channels"]


# ---------------------------------------------------------------------- #
# Video
# ---------------------------------------------------------------------- #
def test_snapshot_returns_jpeg(client):
    response = client.get("/api/cameras/cam1/snapshot")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content[:2] == b"\xff\xd8"  # SOI marker of a JPEG


def test_snapshot_without_frame_returns_503(tasks_path):
    client = TestClient(create_web_app(runtime=_FakeRuntime(tasks_path), start_backend=False))

    response = client.get("/api/cameras/cam1/snapshot")

    assert response.status_code == 503


def test_unknown_camera_returns_404(client):
    assert client.get("/api/cameras/naoexiste/snapshot").status_code == 404


# ---------------------------------------------------------------------- #
# Tasks
# ---------------------------------------------------------------------- #
def test_task_types_include_geometry_kind(client):
    types = {entry["type"]: entry["geometry"] for entry in client.get("/api/task-types").json()}

    assert types["item_counting"] == "line"
    assert types["missing_product"] == "zone"


def test_get_tasks_lists_tasks_with_flags(client):
    tasks = client.get("/api/cameras/cam1/tasks").json()

    assert [task["type"] for task in tasks] == ["item_counting", "missing_product"]
    assert tasks[0]["geometry"] == "line"
    assert tasks[0]["flags"][0]["id"] == "count_threshold"


def test_add_task_appends_to_tasks_yaml(client):
    response = client.post("/api/cameras/cam1/tasks", json={"type": "ppe_compliance"})

    assert response.status_code == 201
    assert [task["type"] for task in client.get("/api/cameras/cam1/tasks").json()][-1] == "ppe_compliance"


def test_add_unknown_task_type_is_rejected(client):
    assert client.post("/api/cameras/cam1/tasks", json={"type": "inventado"}).status_code == 400


def test_delete_task_removes_it(client):
    assert client.delete("/api/cameras/cam1/tasks/0").status_code == 200

    assert [task["type"] for task in client.get("/api/cameras/cam1/tasks").json()] == ["missing_product"]


def test_delete_out_of_range_task_returns_404(client):
    assert client.delete("/api/cameras/cam1/tasks/99").status_code == 404


def test_patch_updates_detect_fps_only(client):
    client.patch("/api/cameras/cam1/tasks/1", json={"detect_fps": 7.5})

    task = client.get("/api/cameras/cam1/tasks").json()[1]
    assert task["detect_fps"] == 7.5
    assert task["params"] == {"zones": []}  # params were left untouched


def test_put_flags_updates_severity_and_channels(client):
    client.put("/api/cameras/cam1/tasks/0/flags", json={
        "flags": [{"id": "count_threshold", "enabled": False,
                   "severity": "critical", "notify": ["log", "db"]}],
    })

    flag = client.get("/api/cameras/cam1/tasks").json()[0]["flags"][0]
    assert flag["enabled"] is False
    assert flag["severity"] == "critical"
    assert flag["notify"] == ["log", "db"]


# ---------------------------------------------------------------------- #
# Calibration — the same validation the Qt GUI uses (config/calibration.py)
# ---------------------------------------------------------------------- #
def test_geometry_saves_counting_line(client):
    response = client.post("/api/cameras/cam1/tasks/0/geometry",
                           json={"points": [[10, 20], [300, 400]]})

    assert response.status_code == 200
    params = client.get("/api/cameras/cam1/tasks").json()[0]["params"]
    assert params["counting_line"] == {"p1": [10, 20], "p2": [300, 400]}


def test_geometry_saves_zone_polygon(client):
    response = client.post("/api/cameras/cam1/tasks/1/geometry", json={
        "points": [[10, 10], [100, 10], [100, 100], [10, 100]],
        "zone_name": "shelf_1",
        "expected_class": "bottle",
    })

    assert response.status_code == 200
    zones = client.get("/api/cameras/cam1/tasks").json()[1]["params"]["zones"]
    assert len(zones) == 1
    assert zones[0]["name"] == "shelf_1"
    assert zones[0]["expected_class"] == "bottle"
    assert zones[0]["polygon"] == [[10, 10], [100, 10], [100, 100], [10, 100]]


def test_geometry_with_wrong_point_count_returns_400(client):
    response = client.post("/api/cameras/cam1/tasks/0/geometry", json={"points": [[10, 20]]})

    assert response.status_code == 400
    body = response.json()
    # The error carries a translation code so the browser can show it in
    # the chosen language; `detail` is the English fallback.
    assert body["code"] == "calibration.line_needs_two_points"
    assert "2 points" in body["detail"]


def test_geometry_zone_without_name_returns_400(client):
    response = client.post("/api/cameras/cam1/tasks/1/geometry",
                           json={"points": [[0, 0], [10, 0], [10, 10]]})

    assert response.status_code == 400
    assert response.json()["code"] == "calibration.zone_name_required"


def test_reload_delegates_to_runtime(client, runtime):
    assert client.post("/api/reload").json()["ok"] is True

    assert runtime.reload_count == 1


# ---------------------------------------------------------------------- #
# ResultsStore.retain — used by AppRuntime.reload_tasks
# ---------------------------------------------------------------------- #
def test_results_store_retain_drops_cameras_without_pipeline():
    """A camera that lost its last task produces no more results; the
    last one must be discarded, otherwise the UIs would forever draw
    boxes from a frozen detection."""
    from pipeline.results_store import ResultsStore

    store = ResultsStore()
    store.set("cam1", ([], []))
    store.set("cam2", ([], []))

    store.retain(["cam1"])

    assert store.get("cam1") is not None
    assert store.get("cam2") is None


# ---------------------------------------------------------------------- #
# build_pipelines — resilience against misconfigured tasks
# ---------------------------------------------------------------------- #
def test_build_pipelines_skips_camera_with_uncalibrated_task(caplog):
    """A task added through an interface and not yet calibrated
    (item_counting without counting_line) used to make the TaskAnalyzer
    blow up during construction and take down the whole startup. Now only
    the affected camera goes without a pipeline, with the reason logged."""
    import logging

    from config.schema import AppSettings, TaskConfig
    from notify.flag_manager import FlagManager
    from pipeline.builder import build_pipelines

    tasks_by_camera = {
        "broken_cam": [TaskConfig(type="item_counting", params={})],  # no counting_line
        "cam_without_tasks": [],
    }

    with caplog.at_level(logging.WARNING):
        pipelines, fps = build_pipelines(
            ["broken_cam", "cam_without_tasks"], tasks_by_camera,
            FlagManager(), AppSettings(),
        )

    assert pipelines == {}
    assert fps == {}
    assert "broken_cam" in caplog.text


# ---------------------------------------------------------------------- #
# Employees
# ---------------------------------------------------------------------- #
def test_enroll_without_photo_or_camera_returns_400(client):
    response = client.post("/api/employees", data={"name": "Jane"})

    assert response.status_code == 400
    assert response.json()["code"] == "api.photo_or_camera_required"


def test_enroll_with_blank_name_returns_400(client):
    response = client.post("/api/employees", data={"name": "   ", "camera_id": "cam1"})

    assert response.status_code == 400
