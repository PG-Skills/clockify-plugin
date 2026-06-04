import os
import stat


def test_learned_path_respeita_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import learned_path

    assert learned_path() == tmp_path / "clockify-horas" / "learned.json"


def test_record_e_list_roundtrip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import learned_path, read_learned, record

    record("Daily da Equipe", "Proj Demo", "Tarefa Demo", ["Etiqueta Demo"], False)
    assert read_learned() == [
        {
            "match": "Daily da Equipe",
            "project_name": "Proj Demo",
            "task_name": "Tarefa Demo",
            "tag_names": ["Etiqueta Demo"],
            "billable": False,
        }
    ]
    if os.name == "posix":
        assert stat.S_IMODE(learned_path().stat().st_mode) == 0o600


def test_record_dedup_por_match(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import read_learned, record

    record("Reunião X", None, "T1", ["G"], False)
    record("  reunião x  ", "Proj Demo", "T2", ["G"], True)  # mesmo match (trim/lower)
    data = read_learned()
    assert len(data) == 1
    assert data[0]["task_name"] == "T2"
    assert data[0]["project_name"] == "Proj Demo"
    assert data[0]["billable"] is True


def test_record_acrescenta_matches_distintos(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import read_learned, record

    record("A", None, "T1", ["G"], False)
    record("B", None, "T2", ["G"], False)
    assert [a["match"] for a in read_learned()] == ["A", "B"]


def test_read_learned_ausente_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import read_learned

    assert read_learned() == []


def test_read_learned_corrompido_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.learned import learned_path, read_learned

    p = learned_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{ não é lista", encoding="utf-8")
    assert read_learned() == []
