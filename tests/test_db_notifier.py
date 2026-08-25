from sqlalchemy import select

from db.models import EventLog
from db.session import get_session, init_db
from notify.flag import Flag
from notify.notifiers.db_notifier import DbNotifier


def test_notify_persists_flag_to_event_log(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")

    flag = Flag(camera_id="cam1", task_type="missing_product", flag_id="missing_product",
                severity="warning", message="Zona 'shelf_1' sem 'bottle'", timestamp=42.0)
    DbNotifier().notify(flag)

    session = get_session()
    events = list(session.scalars(select(EventLog)).all())
    session.close()

    assert len(events) == 1
    assert events[0].camera_id == "cam1"
    assert events[0].message == "Zona 'shelf_1' sem 'bottle'"


def test_notify_swallows_backend_errors(tmp_path, monkeypatch):
    init_db(f"sqlite:///{tmp_path}/test.db")

    def _raise(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr("notify.notifiers.db_notifier.repository.log_event", _raise)

    flag = Flag(camera_id="cam1", task_type="missing_product", flag_id="missing_product",
                severity="warning", message="test")
    DbNotifier().notify(flag)  # must not raise
