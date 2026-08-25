"""
main.py

Ponto de entrada da aplicação:
1. Carrega o cadastro de câmeras (config/cameras.yaml) e as tarefas de
   visão por câmera (config/tasks.yaml)
2. Inicia uma thread de captura por câmera e a thread única de
   inferência (YOLO + tracking, fase 2)
3. Sobe a interface gráfica (PySide6, fase 4): grade com todas as
   câmeras, painel de alertas, calibração e configurações
4. Opcionalmente inicia o narrador de alertas via LLM local (fase 6)
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from camera.camera_manager import CameraManager
from config.loader import load_app_config, load_tasks_config
from db.session import init_db
from gui_qt.app import create_app
from gui_qt.main_window import MainWindow
from notify.flag_manager import FlagManager
from notify.notifiers.desktop import DesktopNotifier
from notify.notifiers.log_notifier import LogNotifier
from pipeline.builder import build_pipelines
from pipeline.inference_engine import InferenceEngine
from pipeline.results_store import ResultsStore

# Importar o pacote "tasks" registra os TaskAnalyzers embutidos
# (contagem de itens, EPI, produto ausente — ver tasks/__init__.py)
# para que os tipos usados em tasks.yaml sejam reconhecidos.
import tasks  # noqa: F401

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")
CAMERAS_CONFIG_PATH = os.path.join(CONFIG_DIR, "cameras.yaml")
TASKS_CONFIG_PATH = os.path.join(CONFIG_DIR, "tasks.yaml")
APP_CONFIG_PATH = os.path.join(CONFIG_DIR, "app.yaml")


def main():
    manager = CameraManager(CAMERAS_CONFIG_PATH)
    manager.start_all()

    app_settings = load_app_config(APP_CONFIG_PATH)
    tasks_by_camera = load_tasks_config(TASKS_CONFIG_PATH)

    # Sempre inicializado (funcionários/embeddings faciais dependem disso,
    # ver db/session.py) — db.enabled só controla o canal "db" abaixo.
    init_db(app_settings.db.url)

    notifiers = {"log": LogNotifier()}
    if app_settings.notify.desktop_enabled:
        notifiers["desktop"] = DesktopNotifier()
    if app_settings.db.enabled:
        from notify.notifiers.db_notifier import DbNotifier
        notifiers["db"] = DbNotifier()
    flag_manager = FlagManager(notifiers=notifiers)
    results_store = ResultsStore()

    camera_ids = [camera_id for camera_id, _name in manager.list_cameras()]
    pipelines, fps_by_camera = build_pipelines(camera_ids, tasks_by_camera, flag_manager, app_settings)

    engine = InferenceEngine(manager, pipelines, results_store, fps_by_camera)
    engine.start()

    narrator = None
    if app_settings.llm.enabled:
        from llm.narrator import AlertNarrator
        narrator = AlertNarrator(
            flag_manager,
            model=app_settings.llm.model,
            interval_seconds=app_settings.llm.interval_seconds,
            max_flags_per_summary=app_settings.llm.max_flags_per_summary,
        )
        narrator.start()

    qt_app = create_app()
    window = MainWindow(manager, results_store, flag_manager, TASKS_CONFIG_PATH, narrator=narrator)
    window.show()
    try:
        qt_app.exec()
    finally:
        if narrator is not None:
            narrator.stop()
        engine.stop()
        manager.stop_all()


if __name__ == "__main__":
    main()
