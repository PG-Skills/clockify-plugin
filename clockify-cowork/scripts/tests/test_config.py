import json

import config


def test_base_dir_prefers_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path / "x"))
    assert config.base_dir() == tmp_path / "x"


def test_base_dir_uses_project_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("CLOCKIFY_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert config.base_dir() == tmp_path / ".clockify"


def test_base_dir_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("CLOCKIFY_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert config.base_dir() == tmp_path / ".clockify"


def test_load_credentials_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    assert config.load_credentials() is None


def test_save_then_load_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="KEY", ics_url=None, workspace_id="ws1", user_id="u1"
    )
    creds = config.load_credentials()
    assert creds == {
        "api_key": "KEY",
        "ics_url": None,
        "workspace_id": "ws1",
        "user_id": "u1",
    }
    # gravado no caminho esperado
    assert json.loads((tmp_path / "credentials.json").read_text())["api_key"] == "KEY"
