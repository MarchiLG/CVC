"""
alerts_panel.py

Painel de alertas: lista os Flags mais recentes emitidos pelo
FlagManager (câmera, severidade, tarefa, mensagem, horário), mais um
resumo em linguagem natural gerado pelo AlertNarrator local (fase 6,
opcional — fica vazio se o LLM estiver desabilitado ou indisponível).
Atualizado pelo mesmo timer de polling da grade de câmeras.
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

_SEVERITY_COLORS = {
    "critical": QColor("#e74c3c"),
    "warning": QColor("#f39c12"),
    "info": QColor("#3498db"),
}
_COLUMNS = ["Hora", "Câmera", "Severidade", "Tarefa", "Mensagem"]


class AlertsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        layout.addWidget(QLabel("Resumo (IA)"))
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setPlaceholderText("Nenhum resumo ainda.")
        self.summary_text.setMaximumHeight(120)
        layout.addWidget(self.summary_text)

        layout.addWidget(QLabel("Alertas"))
        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
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

        for row, flag in enumerate(reversed(flags)):  # mais recente primeiro
            time_str = datetime.fromtimestamp(flag.timestamp).strftime("%H:%M:%S")
            values = [time_str, flag.camera_id, flag.severity, flag.task_type, flag.message]
            color = _SEVERITY_COLORS.get(flag.severity)
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if color is not None:
                    item.setForeground(color)
                self.table.setItem(row, col, item)
