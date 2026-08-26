"""
db_notifier.py

The "db" notification channel: persists the Flag into the event_log
table (see db/repository.log_event) so past alerts can be queried. Its
toggle is independent from the employees/embeddings database, which is
always initialized (see db/session.py) — this channel only controls
whether Flags also become rows in event_log.
"""

import logging

from db import repository
from db.session import get_session

from ..flag import Flag
from .base import Notifier

logger = logging.getLogger("cv_central.notify.db")


class DbNotifier(Notifier):
    name = "db"

    def notify(self, flag: Flag) -> None:
        session = get_session()
        try:
            repository.log_event(
                session, flag.camera_id, flag.task_type, flag.flag_id,
                flag.severity, flag.message, flag.timestamp,
            )
        except Exception:
            logger.exception("Failed to persist flag to the database (%s/%s)", flag.camera_id, flag.flag_id)
        finally:
            session.close()
