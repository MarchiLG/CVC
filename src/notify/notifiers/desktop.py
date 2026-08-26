"""
desktop.py

The "desktop" notification channel: shows a native system notification
through plyer. It fails quietly (logs and moves on) when the
notification backend is not available in the environment — that must
never take down the inference pipeline.
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
            logger.exception("Failed to send desktop notification (%s/%s)", flag.camera_id, flag.flag_id)
