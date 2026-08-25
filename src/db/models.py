"""
models.py

Modelos SQLAlchemy: funcionários e seus embeddings faciais (para
reconhecimento por foto — ver tasks/face_id.py), log de eventos
(Flags persistidos, opcional via notify/notifiers/db_notifier.py) e
log de narrações (fase 6, resumos do LLM local).
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
    """Vetor facial (float32) serializado como bytes — buscas de
    similaridade são feitas em Python (ver db/repository.py), sem
    depender de extensão de vetor no SQLite; adequado ao volume de
    funcionários esperado (dezenas a poucas centenas)."""

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
