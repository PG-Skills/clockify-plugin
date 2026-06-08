import prefs


def test_get_prefs_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    assert prefs.get_prefs() == {"default": {}, "learned": []}


def test_set_default_then_get(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.set_default(
        project="Proj X", task="Dev", tag=None, billable=True, daily_target=8.0
    )
    d = prefs.get_prefs()["default"]
    assert (
        d["project"] == "Proj X" and d["billable"] is True and d["daily_target"] == 8.0
    )


def test_learn_upsert_normalizes_case_and_space(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.learn("Daily", project="Equipe", task="Inovação", tag=None, billable=None)
    prefs.learn(
        "  daily ", project="Equipe", task="Daily", tag=None, billable=False
    )  # upsert
    learned = prefs.get_prefs()["learned"]
    assert len(learned) == 1  # 'Daily' e '  daily ' são a MESMA chave (normalizada)
    assert learned[0]["task"] == "Daily" and learned[0]["match"] == "daily"


def test_forget_learned_normalizes(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.learn("Daily", project="P", task=None, tag=None, billable=None)
    assert prefs.forget_learned("  DAILY ") is True  # normaliza ao esquecer
    assert prefs.forget_learned("daily") is False
    assert prefs.get_prefs()["learned"] == []


def test_clear_resets_default_and_learned(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.set_default(
        project="P", task=None, tag=None, billable=None, daily_target=None
    )
    prefs.learn("x", project="P", task=None, tag=None, billable=None)
    prefs.clear()
    assert prefs.get_prefs() == {"default": {}, "learned": []}
