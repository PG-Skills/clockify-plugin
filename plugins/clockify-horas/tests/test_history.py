import os
import stat


def test_history_path_respeita_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.history import history_path

    assert history_path() == tmp_path / "clockify-horas" / "history.json"


def test_record_e_suggest_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.history import history_path, record_entry, suggest_for

    record_entry("Daily da Equipe", "Equipe Demo", ["Tag"], False, "Proj A")
    s = suggest_for("  daily da equipe  ")  # normaliza trim/lowercase
    assert s == {
        "project_name": "Proj A",
        "task_name": "Equipe Demo",
        "tag_names": ["Tag"],
        "billable": False,
    }
    if os.name == "posix":
        assert stat.S_IMODE(history_path().stat().st_mode) == 0o600


def test_suggest_miss_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.history import suggest_for

    assert suggest_for("nada") is None


def test_record_upsert_sobrescreve(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.history import record_entry, suggest_for

    record_entry("X", "T1", ["G"], False, None)
    record_entry("X", "T2", ["G"], True, "Proj B")
    assert suggest_for("X") == {
        "project_name": "Proj B",
        "task_name": "T2",
        "tag_names": ["G"],
        "billable": True,
    }


def test_read_history_corrompido_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.history import history_path, read_history

    p = history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ não é json", encoding="utf-8")
    assert read_history() == {}
