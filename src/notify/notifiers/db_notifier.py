"""
db_notifier.py

Canal de notificação "db": persiste o Flag na tabela event_log (ver
db/repository.log_event) para consulta histórica dos alertas gerados.
Toggle independente do banco de funcionários/embeddings, que é sempre
inicializado (ver db/session.py) — este canal só controla se os
Flags também viram linhas em event_log.
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
            logger.exception("Falha ao persistir flag no banco (%s/%s)", flag.camera_id, flag.flag_id)
        finally:
            session.close()
