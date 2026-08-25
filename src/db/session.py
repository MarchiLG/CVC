"""
session.py

Engine/sessão do SQLAlchemy para o banco de funcionários e eventos. Um
único engine por processo, configurado uma vez em init_db() (a partir
de app.yaml -> db.url) e reutilizado por get_session() — mesmo padrão
de singleton configurável usado em vision/model_registry.py.

Sempre inicializado no startup da aplicação (main.py), independente do
toggle app.yaml -> db.enabled: esse toggle controla apenas o canal de
notificação "db" (persistência de Flags em EventLog, ver
notify/notifiers/db_notifier.py) — o banco de funcionários/embeddings
é infraestrutura básica para a tarefa face_id e a tela de cadastro.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

DEFAULT_DB_URL = "sqlite:///data/app.db"

_engine = None
_SessionFactory = None


def init_db(db_url: str = DEFAULT_DB_URL) -> None:
    global _engine, _SessionFactory

    if db_url.startswith("sqlite:///") and db_url != "sqlite:///:memory:":
        db_path = db_url[len("sqlite:///"):]
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    _engine = create_engine(db_url)
    Base.metadata.create_all(_engine)
    _SessionFactory = sessionmaker(bind=_engine)


def get_session() -> Session:
    if _SessionFactory is None:
        init_db()
    return _SessionFactory()
