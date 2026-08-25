"""
log_notifier.py

Canal de notificação "log": registra o Flag via logging padrão do
Python. Serve como fallback sempre disponível, independente de outros
canais (desktop, banco de dados, etc.) estarem configurados ou não.
"""

import logging

from ..flag import Flag
from .base import Notifier

logger = logging.getLogger("cv_central.flags")


class LogNotifier(Notifier):
    name = "log"

    def notify(self, flag: Flag) -> None:
        logger.info(
            "[%s] %s/%s (%s): %s",
            flag.severity.upper(), flag.camera_id, flag.flag_id, flag.task_type, flag.message,
        )
