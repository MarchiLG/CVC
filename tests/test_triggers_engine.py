from config.triggers_schema import TriggerAction, TriggerCondition, TriggerRule, TriggersSettings
from notify.flag import Flag
from triggers.engine import TriggerEngine


def _flag(**overrides):
    defaults = dict(camera_id="cam1", task_type="item_counting", flag_id="count_threshold", severity="warning")
    defaults.update(overrides)
    return Flag(**defaults)


def _settings(mode, rules):
    return TriggersSettings(mode=mode, rules=rules)


def test_auto_mode_executes_immediately(monkeypatch):
    import triggers.engine as mod

    executed = []
    monkeypatch.setattr(mod.TriggerEngine, "_execute", lambda self, action, flag: executed.append((action.type, flag.flag_id)))

    rule = TriggerRule(id="r1", condition=TriggerCondition(flag_id="count_threshold"),
                        actions=[TriggerAction(type="http_webhook", target={"url": "http://x"})])
    engine = TriggerEngine(_settings("auto", [rule]))

    engine.on_flag(_flag())

    assert executed == [("http_webhook", "count_threshold")]
    assert engine.pending() == []


def test_ask_mode_queues_pending_action_instead_of_executing(monkeypatch):
    import triggers.engine as mod

    executed = []
    monkeypatch.setattr(mod.TriggerEngine, "_execute", lambda self, action, flag: executed.append(action.type))

    rule = TriggerRule(id="r1", condition=TriggerCondition(flag_id="count_threshold"),
                        actions=[TriggerAction(type="http_webhook", target={})])
    engine = TriggerEngine(_settings("ask", [rule]))

    engine.on_flag(_flag())

    assert executed == []
    pending = engine.pending()
    assert len(pending) == 1
    assert pending[0].rule_id == "r1"


def test_disabled_rule_never_matches():
    rule = TriggerRule(id="r1", enabled=False, condition=TriggerCondition(),
                        actions=[TriggerAction(type="http_webhook", target={})])
    engine = TriggerEngine(_settings("auto", [rule]))

    engine.on_flag(_flag())

    assert engine.pending() == []


def test_condition_wildcards_match_any_value():
    rule = TriggerRule(id="r1", condition=TriggerCondition(), actions=[])
    engine = TriggerEngine(_settings("ask", [rule]))
    # No actions on the rule, but on_flag must not raise or filter it out
    # on grounds of the wildcard condition not matching.
    engine.on_flag(_flag(camera_id="anything", task_type="anything", flag_id="anything"))
    assert engine.pending() == []  # no actions to queue, not a failure


def test_condition_field_mismatch_prevents_match(monkeypatch):
    import triggers.engine as mod
    executed = []
    monkeypatch.setattr(mod.TriggerEngine, "_execute", lambda self, action, flag: executed.append(action.type))

    rule = TriggerRule(id="r1", condition=TriggerCondition(camera_id="cam2"),
                        actions=[TriggerAction(type="http_webhook", target={})])
    engine = TriggerEngine(_settings("auto", [rule]))

    engine.on_flag(_flag(camera_id="cam1"))

    assert executed == []


def test_approve_executes_and_removes_from_pending(monkeypatch):
    import triggers.engine as mod
    executed = []
    monkeypatch.setattr(mod.TriggerEngine, "_execute", lambda self, action, flag: executed.append(action.type))

    rule = TriggerRule(id="r1", condition=TriggerCondition(),
                        actions=[TriggerAction(type="http_webhook", target={})])
    engine = TriggerEngine(_settings("ask", [rule]))
    engine.on_flag(_flag())
    pending_id = engine.pending()[0].id

    assert engine.approve(pending_id) is True
    assert executed == ["http_webhook"]
    assert engine.pending() == []


def test_approve_unknown_id_returns_false():
    engine = TriggerEngine(_settings("ask", []))
    assert engine.approve("does-not-exist") is False


def test_deny_removes_without_executing(monkeypatch):
    import triggers.engine as mod
    executed = []
    monkeypatch.setattr(mod.TriggerEngine, "_execute", lambda self, action, flag: executed.append(action.type))

    rule = TriggerRule(id="r1", condition=TriggerCondition(),
                        actions=[TriggerAction(type="http_webhook", target={})])
    engine = TriggerEngine(_settings("ask", [rule]))
    engine.on_flag(_flag())
    pending_id = engine.pending()[0].id

    assert engine.deny(pending_id) is True
    assert executed == []
    assert engine.pending() == []


def test_deny_unknown_id_returns_false():
    engine = TriggerEngine(_settings("ask", []))
    assert engine.deny("does-not-exist") is False


def test_reload_swaps_settings_in_place():
    engine = TriggerEngine(_settings("ask", []))
    new_settings = _settings("auto", [])

    engine.reload(new_settings)

    assert engine.settings is new_settings
