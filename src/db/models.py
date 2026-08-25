"""
models.py

SQLAlchemy models: employees and their face embeddings (for photo-based
recognition — see tasks/face_id.py), the event log (persisted Flags,
optional through notify/notifiers/db_notifier.py) and the narration log
(summaries from the local LLM).
"""

import time

from sqlalchemy import Float, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

    embeddings: Mapped[list["FaceEmbedding"]] = relationship(
        back_populates="employee", cascade="all, delete-orphan"
    )


class FaceEmbedding(Base):
    """Face vector (float32) serialized as bytes — similarity searches
    happen in Python (see db/repository.py), without depending on a
    vector extension in SQLite; adequate for the expected number of
    employees (tens to a few hundred)."""

    __tablename__ = "face_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)

    employee: Mapped["Employee"] = relationship(back_populates="embeddings")


class EventLog(Base):
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[str] = mapped_column(String, nullable=False)
    task_type: Mapped[str] = mapped_column(String, nullable=False)
    flag_id: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, default="")
    timestamp: Mapped[float] = mapped_column(Float, default=time.time)


class NarrationLog(Base):
    __tablename__ = "narration_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)
