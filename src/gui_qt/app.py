"""
app.py

Bootstrap da QApplication — instancia o QApplication único do
processo antes de qualquer QWidget ser criado.
"""

import sys

from PySide6.QtWidgets import QApplication


def create_app() -> QApplication:
    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication(sys.argv)
