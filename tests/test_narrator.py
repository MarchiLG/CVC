from sqlalchemy import select

from db.models import NarrationLog
from db.session import get_session, init_db
from llm.narrator import AlertNarrator
from notify.flag import Flag
from notify.flag_manager import FlagManager


class _FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, prompt):
        self.calls.append(prompt)
        if not self.responses:
            return None
        return self.responses.pop(0)


def _flag(flag_id, timestamp, message="msg"):
    return Flag(camera_id="cam1", task_type="test", flag_id=flag_id,
                severity="info", message=message, timestamp=timestamp)


def test_run_once_returns_none_when_no_flags():
    flag_manager = FlagManager()
    client = _FakeClient(["summary"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    result = narrator.run_once()

    assert result is None
    assert client.calls == []


def test_run_once_generates_summary_for_new_flags(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0))
    client = _FakeClient(["resumo 1"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    result = narrator.run_once()

    assert result == "resumo 1"
    assert narrator.latest_summary() == "resumo 1"
    assert len(client.calls) == 1


def test_run_once_skips_when_no_new_flags_since_last_summary(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0))
    client = _FakeClient(["resumo 1", "resumo 2"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    narrator.run_once()
    result = narrator.run_once()  # nothing new since the last summary

    assert result is None
    assert len(client.calls) == 1  # the second call should not have happened


def test_run_once_generates_again_when_newer_flag_arrives(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0))
    client = _FakeClient(["resumo 1", "resumo 2"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    narrator.run_once()
    flag_manager.emit(_flag("f2", timestamp=200.0))
    result = narrator.run_once()

    assert result == "resumo 2"
    assert len(client.calls) == 2


def test_run_once_retries_on_next_call_when_ollama_fails(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0))
    client = _FakeClient([None, "resumo depois de falhar"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    first = narrator.run_once()
    second = narrator.run_once()  # same (still-newest) flags retried since the mark wasn't advanced

    assert first is None
    assert second == "resumo depois de falhar"
    assert len(client.calls) == 2


def test_run_once_persists_summary_to_narration_log(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0))
    client = _FakeClient(["resumo persistido"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    narrator.run_once()

    session = get_session()
    narrations = list(session.scalars(select(NarrationLog)).all())
    session.close()

    assert len(narrations) == 1
    assert narrations[0].summary_text == "resumo persistido"


def test_prompt_includes_flag_details(tmp_path):
    init_db(f"sqlite:///{tmp_path}/test.db")
    flag_manager = FlagManager(cooldown_seconds=0)
    flag_manager.emit(_flag("f1", timestamp=100.0, message="Pessoa #3 sem: helmet"))
    client = _FakeClient(["resumo"])
    narrator = AlertNarrator(flag_manager, model="test", client=client)

    narrator.run_once()

    assert "Pessoa #3 sem: helmet" in client.calls[0]
    assert "cam1" in client.calls[0]
