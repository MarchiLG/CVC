import numpy as np

from db import repository
from db.session import get_session, init_db


def _init_temp_db(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")


def test_add_employee_and_list(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    repository.add_employee(session, "Alice")
    repository.add_employee(session, "Bob")

    names = {e.name for e in repository.list_employees(session)}
    assert names == {"Alice", "Bob"}
    session.close()


def test_find_best_match_returns_closest_employee_above_threshold(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    alice = repository.add_employee(session, "Alice")
    bob = repository.add_employee(session, "Bob")
    repository.add_face_embedding(session, alice.id, np.array([1.0, 0.0, 0.0], dtype=np.float32))
    repository.add_face_embedding(session, bob.id, np.array([0.0, 1.0, 0.0], dtype=np.float32))

    query = np.array([0.95, 0.05, 0.0], dtype=np.float32)  # very close to Alice's vector
    employee, score = repository.find_best_match(session, query, threshold=0.8)

    assert employee.name == "Alice"
    assert score > 0.9
    session.close()


def test_find_best_match_below_threshold_returns_none(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    alice = repository.add_employee(session, "Alice")
    repository.add_face_embedding(session, alice.id, np.array([1.0, 0.0, 0.0], dtype=np.float32))

    query = np.array([0.0, 1.0, 0.0], dtype=np.float32)  # orthogonal, similarity ~0
    employee, score = repository.find_best_match(session, query, threshold=0.5)

    assert employee is None
    assert score < 0.5
    session.close()


def test_find_best_match_with_no_employees_returns_none(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    employee, score = repository.find_best_match(session, np.array([1.0, 0.0], dtype=np.float32))

    assert employee is None
    assert score == -1.0
    session.close()


def test_log_event_persists_flag_data(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    event = repository.log_event(
        session, camera_id="cam1", task_type="ppe_compliance", flag_id="missing_ppe",
        severity="critical", message="Pessoa #1 sem: helmet", timestamp=123.0,
    )

    assert event.id is not None
    session.close()


def test_add_narration_persists_summary(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    narration = repository.add_narration(session, "Resumo de teste")

    assert narration.id is not None
    assert narration.summary_text == "Resumo de teste"
    session.close()


def test_employee_embeddings_relationship(tmp_path):
    _init_temp_db(tmp_path)
    session = get_session()

    alice = repository.add_employee(session, "Alice")
    repository.add_face_embedding(session, alice.id, np.array([1.0, 0.0], dtype=np.float32))
    repository.add_face_embedding(session, alice.id, np.array([1.0, 0.1], dtype=np.float32))

    reloaded = repository.list_employees(session)[0]
    assert len(reloaded.embeddings) == 2
    session.close()
