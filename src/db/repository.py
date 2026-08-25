"""
repository.py

Operações de CRUD sobre funcionários/embeddings faciais e persistência
de eventos (Flags). A busca do funcionário mais parecido é feita em
Python via similaridade de cosseno — ver nota em models.py sobre por
que não usamos uma extensão de vetor no SQLite aqui.
"""

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Employee, EventLog, FaceEmbedding, NarrationLog


def add_employee(session: Session, name: str) -> Employee:
    employee = Employee(name=name)
    session.add(employee)
    session.commit()
    session.refresh(employee)
    return employee


def add_face_embedding(session: Session, employee_id: int, embedding) -> FaceEmbedding:
    record = FaceEmbedding(
        employee_id=employee_id,
        vector=np.asarray(embedding, dtype=np.float32).tobytes(),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


def list_employees(session: Session) -> list[Employee]:
    return list(session.scalars(select(Employee)).all())


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_best_match(session: Session, embedding, threshold: float = 0.45):
    """Retorna (Employee, similaridade) do funcionário mais parecido
    acima do limiar, ou (None, melhor_similaridade) se ninguém bater
    (ou não houver funcionários cadastrados)."""
    query_vec = np.asarray(embedding, dtype=np.float32)

    best_employee = None
    best_score = -1.0
    for record in session.scalars(select(FaceEmbedding)).all():
        candidate_vec = np.frombuffer(record.vector, dtype=np.float32)
        score = _cosine_similarity(query_vec, candidate_vec)
        if score > best_score:
            best_score = score
            best_employee = record.employee

    if best_employee is not None and best_score >= threshold:
        return best_employee, best_score
    return None, best_score


def log_event(
    session: Session, camera_id: str, task_type: str, flag_id: str,
    severity: str, message: str, timestamp: float,
) -> EventLog:
    event = EventLog(
        camera_id=camera_id, task_type=task_type, flag_id=flag_id,
        severity=severity, message=message, timestamp=timestamp,
    )
    session.add(event)
    session.commit()
    return event


def add_narration(session: Session, summary_text: str) -> NarrationLog:
    narration = NarrationLog(summary_text=summary_text)
    session.add(narration)
    session.commit()
    return narration
