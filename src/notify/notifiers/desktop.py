"""
desktop.py

Canal de notificação "desktop": mostra uma notificação nativa do
sistema via plyer. Falha de forma silenciosa (loga e segue) se o
backend de notificação não estiver disponível no ambiente — isso não
deve derrubar o pipeline de inferência.
"""

import logging

from plyer import notification

from ..flag import Flag
from .base import Notifier

logger = logging.getLogger("cv_central.notify.desktop")


class DesktopNotifier(Notifier):
    name = "desktop"

    def notify(self, flag: Flag) -> None:
        try:
            notification.notify(
                title=f"{flag.camera_id} — {flag.severity.upper()}",
                message=flag.message or f"{flag.task_type}/{flag.flag_id}",
                timeout=8,
            )
        except Exception:
            logger.exception("Falha ao enviar notificação desktop (%s/%s)", flag.camera_id, flag.flag_id)
