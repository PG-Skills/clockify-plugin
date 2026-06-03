import json

from clockify_horas.config import Defaults, load_config, load_defaults


def test_load_config_le_variaveis(monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "key123"
    assert cfg.workspace_id == "ws1"
    assert cfg.ics_url == "https://x/cal.ics"


def test_load_config_falta_chave_levanta(monkeypatch):
    # use_dotenv=False evita que um .env local repopule a chave deletada
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    try:
        load_config(use_dotenv=False)
    except ValueError as e:
        assert "CLOCKIFY_API_KEY" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_load_defaults_le_json(tmp_path):
    p = tmp_path / "defaults.json"
    p.write_text(
        json.dumps(
            {
                "task_name": ".Célula de Inovação: Time IA",
                "tag_name": "Atividades Internas",
                "billable": False,
                "daily_target_hours": 8.0,
            }
        ),
        encoding="utf-8",
    )
    d = load_defaults(p)
    assert d == Defaults(
        task_name=".Célula de Inovação: Time IA",
        tag_name="Atividades Internas",
        billable=False,
        daily_target_hours=8.0,
    )


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
