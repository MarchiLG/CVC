"""
alerts_panel.py

Alerts panel: lists the most recent Flags emitted by the FlagManager
(camera, severity, task, message, time), plus a natural-language
summary produced by the local AlertNarrator (optional — it stays empty
when the LLM is disabled or unavailable). Refreshed by the same polling
timer as the camera grid.

Alert messages are translated here through Flag.message_key, so the
panel follows app.yaml -> ui.language; flags without a key fall back to
Flag.message, which is always English.
"""

from datetime import datetime

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from i18n import DEFAULT_LANGUAGE, t

_SEVERITY_COLORS = {
    "critical": QColor("#e74c3c"),
    "warning": QColor("#f39c12"),
    "info": QColor("#3498db"),
}


class AlertsPanel(QWidget):
    def __init__(self, parent=None, language: str = DEFAULT_LANGUAGE):
        super().__init__(parent)
        self.language = language

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel(t("alerts.summary_label", language)))
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText(t("qt.summary_placeholder", language))
        self.summary_text.setMaximumHeight(120)
        layout.addWidget(self.summary_text)

        layout.addWidget(QLabel(t("alerts.title", language)))
        columns = [
            t("qt.col.time", language),
            t("qt.col.camera", language),
            t("qt.col.severity", language),
            t("qt.col.task", language),
            t("qt.col.message", language),
        ]
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

    def update_summary(self, summary: str | None):
        if summary is not None and summary != self.summary_text.toPlainText():
            self.summary_text.setPlainText(summary)

    def update_flags(self, flags: list):
        self.table.setRowCount(len(flags))

        for row, flag in enumerate(reversed(flags)):  # most recent first
            time_str = datetime.fromtimestamp(flag.timestamp).strftime("%H:%M:%S")
            values = [
                time_str,
                flag.camera_id,
                t(f"severity.{flag.severity}", self.language),
                flag.task_type,
                self._message(flag),
            ]
            color = _SEVERITY_COLORS.get(flag.severity)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if color is not None:
                    item.setForeground(color)
                self.table.setItem(row, col, item)

    def _message(self, flag) -> str:
        """Translated text of the alert, falling back to the English one
        already rendered by the analyzer when there is no key."""
        key = getattr(flag, "message_key", "")
        if not key:
            return flag.message
        return t(key, self.language, **getattr(flag, "message_params", {}))
