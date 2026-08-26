"""
app.py

QApplication bootstrap — creates the single QApplication of the process
before any QWidget exists.
"""

import sys

from PySide6.QtWidgets import QApplication


def create_app() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication(sys.argv)
