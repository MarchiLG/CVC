"""
main.py

Entry point of the native desktop GUI (PySide6/Qt) — the interface that
does NOT need a browser. Started through ./run.sh.

The whole backend (cameras, inference, notifications, narrator) is
assembled by bootstrap.AppRuntime, the same one used by the web UI in
main_web.py — only Qt-specific wiring lives here.

For the web interface (HTML/CSS/JS in the browser), see src/main_web.py
and ./run-html.sh.
"""

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

from security import env_vault

# Unlocks (or, on first run, creates) the encrypted camera-credential
# store BEFORE anything that might read a camera URL — asks for the
# password on the terminal, exits on cancellation/too many attempts.
# See src/security/env_vault.py.
env_vault.unlock_interactive(os.path.join(os.path.dirname(__file__), ".."))

from bootstrap import AppRuntime
from gui_qt.app import create_app
from gui_qt.main_window import MainWindow


def main():
    runtime = AppRuntime.create()
    runtime.start()

    qt_app = create_app()
    window = MainWindow(
        runtime.camera_manager,
        runtime.results_store,
        runtime.flag_manager,
        runtime.tasks_yaml_path,
        narrator=runtime.narrator,
        language=runtime.app_settings.ui.language,
    )
    window.show()
    try:
        qt_app.exec()
    finally:
        runtime.stop()


if __name__ == "__main__":
    main()
