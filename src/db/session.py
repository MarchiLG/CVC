"""
session.py

SQLAlchemy engine/session for the employees and events database. One
engine per process, configured once in init_db() (from app.yaml ->
db.url) and reused by get_session() — the same configurable-singleton
pattern used in vision/model_registry.py.

It is always initialized at application startup (bootstrap.py),
regardless of the app.yaml -> db.enabled toggle: that toggle only
controls the "db" notification channel (persisting Flags into EventLog,
see notify/notifiers/db_notifier.py) — the employees/embeddings
database is basic infrastructure for the face_id task and the
enrollment screen.
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
