"""
log_notifier.py

The "log" notification channel: records the Flag through Python's
standard logging. It serves as an always-available fallback, whether or
not the other channels (desktop, database, etc.) are configured.
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
