"""
bootstrap.py

Assembles and starts the ENTIRE application backend (cameras, inference
pipelines, notifiers, database and LLM narrator) without knowing
anything about graphical interfaces.

It exists so that both available interfaces share exactly the same
backend:

    src/main.py       -> native desktop GUI (PySide6/Qt), no browser
    src/main_web.py   -> web UI (HTML/CSS/JS) served by FastAPI

Each entry point only does: `runtime = AppRuntime.create(); runtime.start()`,
uses `runtime.<component>` to read frames/alerts, and calls
`runtime.stop()` on exit. Any change to how the backend is composed (a
new notifier, another configuration source) is made here once and
applies to both UIs.
"""

import logging
import os

from camera.camera_manager import CameraManager
from config.loader import load_app_config, load_tasks_config
from config.schema import AppSettings
from db.session import init_db
from notify.flag_manager import FlagManager
from notify.notifiers.log_notifier import LogNotifier
from pipeline.builder import build_pipelines
from pipeline.inference_engine import InferenceEngine
from pipeline.results_store import ResultsStore

# Importing the "tasks" package registers the built-in TaskAnalyzers
# (item counting, PPE, missing product, face_id — see tasks/__init__.py)
# so the types used in tasks.yaml are recognized when the pipelines are
# assembled.
import tasks  # noqa: F401

logger = logging.getLogger("cv_central.bootstrap")

# Default configuration paths, relative to the project root
# (src/../config). Overridable in AppRuntime.create() — the tests use
# that to point at a temporary directory.
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
CAMERAS_CONFIG_PATH = os.path.join(CONFIG_DIR, "cameras.yaml")
TASKS_CONFIG_PATH = os.path.join(CONFIG_DIR, "tasks.yaml")
APP_CONFIG_PATH = os.path.join(CONFIG_DIR, "app.yaml")


class AppRuntime:
    """Groups the live backend components and their lifecycle.

    Not a singleton: the web UI keeps the instance in web/server.py and
    the Qt GUI passes the components to MainWindow. Build it through
    AppRuntime.create() (__init__ only takes already-assembled pieces,
    which makes constructing a fake runtime in tests easy).
    """

    def __init__(
        self,
        camera_manager: CameraManager,
        results_store: ResultsStore,
        flag_manager: FlagManager,
        engine: InferenceEngine,
        app_settings: AppSettings,
        tasks_yaml_path: str,
        cameras_yaml_path: str,
        narrator=None,
    ):
        self.camera_manager = camera_manager
        self.results_store = results_store
        self.flag_manager = flag_manager
        self.engine = engine
        self.app_settings = app_settings
        self.tasks_yaml_path = tasks_yaml_path
        self.cameras_yaml_path = cameras_yaml_path
        self.narrator = narrator

        self._started = False

    # ------------------------------------------------------------------ #
    # Construction
    # ------------------------------------------------------------------ #
    @classmethod
    def create(
        cls,
        cameras_yaml_path: str = CAMERAS_CONFIG_PATH,
        tasks_yaml_path: str = TASKS_CONFIG_PATH,
        app_yaml_path: str = APP_CONFIG_PATH,
    ) -> "AppRuntime":
        """Reads the three configuration sources and assembles the whole
        backend — without starting any thread yet (that is start())."""
        app_settings = load_app_config(app_yaml_path)
        tasks_by_camera = load_tasks_config(tasks_yaml_path)

        # Always initialized (employees/face embeddings depend on it,
        # see db/session.py) — app.yaml -> db.enabled only controls the
        # "db" notification channel just below.
        init_db(app_settings.db.url)

        camera_manager = CameraManager(cameras_yaml_path)
        flag_manager = FlagManager(notifiers=cls._build_notifiers(app_settings))
        results_store = ResultsStore()

        camera_ids = [camera_id for camera_id, _name in camera_manager.list_cameras()]
        pipelines, fps_by_camera = build_pipelines(
            camera_ids, tasks_by_camera, flag_manager, app_settings
        )
        engine = InferenceEngine(camera_manager, pipelines, results_store, fps_by_camera)

        return cls(
            camera_manager=camera_manager,
            results_store=results_store,
            flag_manager=flag_manager,
            engine=engine,
            app_settings=app_settings,
            tasks_yaml_path=tasks_yaml_path,
            cameras_yaml_path=cameras_yaml_path,
            narrator=cls._build_narrator(app_settings, flag_manager),
        )

    @staticmethod
    def _build_notifiers(app_settings: AppSettings) -> dict:
        """Notification channels enabled in app.yaml. The "log" channel
        is always present; "desktop" and "db" are optional and their
        imports are deferred so that a missing dependency does not take
        down the whole application."""
        notifiers = {"log": LogNotifier()}

        if app_settings.notify.desktop_enabled:
            from notify.notifiers.desktop import DesktopNotifier
            notifiers["desktop"] = DesktopNotifier()

        if app_settings.db.enabled:
            from notify.notifiers.db_notifier import DbNotifier
            notifiers["db"] = DbNotifier()

        return notifiers

    @staticmethod
    def _build_narrator(app_settings: AppSettings, flag_manager: FlagManager):
        """LLM narrator (optional). Returns None when llm.enabled is
        false in app.yaml — both UIs treat None as "no summary
        available"."""
        if not app_settings.llm.enabled:
            return None

        from llm.narrator import AlertNarrator
        return AlertNarrator(
            flag_manager,
            model=app_settings.llm.model,
            interval_seconds=app_settings.llm.interval_seconds,
            max_flags_per_summary=app_settings.llm.max_flags_per_summary,
            language=app_settings.ui.language,
        )

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Starts the background threads: one capture per camera, the
        single inference thread and (when enabled) the narrator.
        Idempotent — calling it twice does not duplicate threads."""
        if self._started:
            return
        self._started = True

        self.camera_manager.start_all()
        self.engine.start()
        if self.narrator is not None:
            self.narrator.start()

        logger.info(
            "Backend started: %d camera(s), %d inference pipeline(s).",
            len(self.camera_manager.list_cameras()),
            len(self.engine.pipelines),
        )

    def stop(self) -> None:
        """Stops everything in the reverse order of start(). Idempotent."""
        if not self._started:
            return
        self._started = False

        if self.narrator is not None:
            self.narrator.stop()
        self.engine.stop()
        self.camera_manager.stop_all()

        logger.info("Backend stopped.")

    def reload_tasks(self) -> int:
        """Re-reads tasks.yaml and rebuilds the inference pipelines
        without restarting the application. Returns how many pipelines
        ended up active.

        Used by the web UI after saving tasks/calibration, so the edit
        takes effect immediately. The inference thread is stopped and
        recreated (InferenceEngine.stop() waits for the thread to
        finish, so two are never running at once); the already-loaded
        YOLO weights are reused by the ModelRegistry, which makes the
        rebuild cheap.
        """
        was_running = self._started
        if was_running:
            self.engine.stop()

        tasks_by_camera = load_tasks_config(self.tasks_yaml_path)
        camera_ids = [camera_id for camera_id, _name in self.camera_manager.list_cameras()]
        pipelines, fps_by_camera = build_pipelines(
            camera_ids, tasks_by_camera, self.flag_manager, self.app_settings
        )

        # Cameras that lost their pipeline no longer produce results:
        # without this, their last detection would stay frozen in the
        # store and the UIs would keep drawing those boxes forever.
        self.results_store.retain(pipelines.keys())

        self.engine = InferenceEngine(self.camera_manager, pipelines, self.results_store, fps_by_camera)
        if was_running:
            self.engine.start()

        logger.info("Pipelines reloaded from %s: %d active.",
                    self.tasks_yaml_path, len(pipelines))
        return len(pipelines)

    # ------------------------------------------------------------------ #
    # Queries used by the UIs
    # ------------------------------------------------------------------ #
    def latest_summary(self) -> str | None:
        """Latest summary from the LLM narrator, or None when the
        narrator is disabled or has not produced anything yet."""
        if self.narrator is None:
            return None
        return self.narrator.latest_summary()
