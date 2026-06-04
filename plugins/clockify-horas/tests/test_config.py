from clockify_horas.config import Defaults, load_config, load_defaults


def test_load_config_env_tem_precedencia(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "key123"
    assert cfg.workspace_id == "ws1"
    assert cfg.ics_url == "https://x/cal.ics"


def test_load_config_le_do_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    from clockify_horas.config import write_raw

    write_raw(
        {
            "clockify": {"api_key": "fileKey", "workspace_id": "fileWs"},
            "outlook": {"ics_url": "https://file/cal.ics"},
        }
    )
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "fileKey"
    assert cfg.workspace_id == "fileWs"
    assert cfg.ics_url == "https://file/cal.ics"


def test_load_config_falta_chave_levanta(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    try:
        load_config(use_dotenv=False)
    except ValueError as e:
        assert "CLOCKIFY_API_KEY" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_load_config_ics_opcional(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("OUTLOOK_ICS_URL", raising=False)
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "w")
    cfg = load_config(use_dotenv=False)
    assert cfg.ics_url == ""


def test_config_path_respeita_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import config_path

    assert config_path() == tmp_path / "clockify-horas" / "config.json"


def test_write_raw_cria_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import os
    import stat

    from clockify_horas.config import config_path, read_raw, write_raw

    p = write_raw({"defaults": {"task_name": "X"}})
    assert p == config_path()
    assert read_raw() == {"defaults": {"task_name": "X"}}
    if os.name == "posix":  # chmod 600 é POSIX-only; no Windows é no-op
        assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_read_raw_ausente_retorna_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import read_raw

    assert read_raw() == {}


def test_load_defaults_do_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import write_raw

    write_raw(
        {
            "defaults": {
                "task_name": "Equipe Demo",
                "tag_name": "Atividades Internas",
                "billable": False,
                "daily_target_hours": 8.0,
            }
        }
    )
    d = load_defaults()
    assert d == Defaults(
        task_name="Equipe Demo",
        tag_name="Atividades Internas",
        billable=False,
        daily_target_hours=8.0,
    )


def test_load_defaults_sem_secao_tolerante(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_defaults, write_raw

    write_raw({"clockify": {"api_key": "K", "workspace_id": "W"}})  # sem 'defaults'
    d = load_defaults()
    assert d.task_name is None
    assert d.tag_name is None
    assert d.billable is None
    assert d.daily_target_hours == 8.0
    assert d.project is None


def test_load_defaults_parcial_nao_levanta(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_defaults, write_raw

    write_raw({"defaults": {"task_name": "Só isso"}})
    d = load_defaults()  # não levanta
    assert d.task_name == "Só isso"
    assert d.tag_name is None
    assert d.billable is None
    assert d.daily_target_hours == 8.0


def test_load_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import Override, load_overrides, write_raw

    write_raw(
        {
            "overrides": [
                {
                    "match": "Cliente Demo",
                    "task_name": "Assinatura",
                    "tag_name": "Implantação",
                    "billable": True,
                }
            ]
        }
    )
    assert load_overrides() == [
        Override(
            match="Cliente Demo",
            task_name="Assinatura",
            tag_name="Implantação",
            billable=True,
        )
    ]


def test_load_overrides_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_overrides, write_raw

    write_raw({})
    assert load_overrides() == []


def test_load_overrides_incompleto_levanta(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_overrides, write_raw

    write_raw({"overrides": [{"match": "X"}]})
    try:
        load_overrides()
    except ValueError as e:
        assert "override incompleto" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_load_defaults_com_projeto(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_defaults, write_raw

    write_raw(
        {
            "defaults": {
                "task_name": "T",
                "tag_name": "G",
                "billable": False,
                "daily_target_hours": 8.0,
                "project": "Proj A",
            }
        }
    )
    assert load_defaults().project == "Proj A"


def test_load_defaults_sem_projeto_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_defaults, write_raw

    write_raw(
        {
            "defaults": {
                "task_name": "T",
                "tag_name": "G",
                "billable": False,
                "daily_target_hours": 8.0,
            }
        }
    )
    assert load_defaults().project is None


def test_load_defaults_billable_false_explicito(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_defaults, write_raw

    write_raw({"defaults": {"task_name": "T", "billable": False}})
    d = load_defaults()
    assert d.billable is False  # explícito False, não None


def test_load_overrides_com_projeto(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_overrides, write_raw

    write_raw(
        {
            "overrides": [
                {
                    "match": "M",
                    "task_name": "T",
                    "tag_name": "G",
                    "billable": True,
                    "project": "Proj B",
                }
            ]
        }
    )
    ov = load_overrides()
    assert ov[0].project == "Proj B"
