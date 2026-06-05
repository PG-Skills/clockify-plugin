"""Store SQLite de preferências NÃO-sensíveis por usuário.

A chave do Clockify NUNCA entra aqui. Travam: roundtrip do default (upsert sem
duplicar), upsert de learned por match normalizado (case/espaços), múltiplos
matches e user inexistente. O DB é isolado por teste via env PREFS_DB + tmp_path."""

import pytest

from clockify_mcp import prefs
from clockify_mcp.settings import get_settings


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Cada teste escreve num DB próprio em tmp_path; nunca toca /data."""
    monkeypatch.setenv("PREFS_DB", str(tmp_path / "prefs.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_set_default_roundtrip():
    prefs.set_default(
        "u1", project="P", task="T", tag="G", billable=True, daily_target=8.0
    )
    out = prefs.get_prefs("u1")
    assert out["default"] == {
        "project": "P",
        "task": "T",
        "tag": "G",
        "billable": True,
        "daily_target": 8.0,
    }
    assert out["learned"] == []


def test_set_default_updates_not_duplicates():
    prefs.set_default("u1", project="P", task="T")
    prefs.set_default("u1", project="P2", task="T2", billable=False)
    out = prefs.get_prefs("u1")
    assert out["default"]["project"] == "P2"
    assert out["default"]["task"] == "T2"
    assert out["default"]["billable"] is False
    # Uma só linha por user_id (PK) — get_prefs devolve um único default.
    assert isinstance(out["default"], dict)


def test_learn_same_match_upserts():
    prefs.learn("u1", "Reunião", project="P1", task="T1")
    prefs.learn("u1", "  reuniÃO  ", project="P2", task="T2", billable=True)
    out = prefs.get_prefs("u1")
    assert len(out["learned"]) == 1
    item = out["learned"][0]
    assert item["project"] == "P2"
    assert item["task"] == "T2"
    assert item["billable"] is True


def test_learn_different_matches():
    prefs.learn("u1", "Reunião", project="P1")
    prefs.learn("u1", "Daily", project="P2")
    prefs.learn("u1", "Code review", project="P3")
    out = prefs.get_prefs("u1")
    assert len(out["learned"]) == 3
    projects = {i["project"] for i in out["learned"]}
    assert projects == {"P1", "P2", "P3"}


def test_unknown_user():
    out = prefs.get_prefs("ghost")
    assert out == {"default": None, "learned": []}


def test_users_are_isolated():
    prefs.set_default("u1", project="P1")
    prefs.learn("u1", "Reunião", project="P1")
    prefs.set_default("u2", project="P2")
    assert prefs.get_prefs("u2")["default"]["project"] == "P2"
    assert prefs.get_prefs("u2")["learned"] == []
    assert prefs.get_prefs("u1")["default"]["project"] == "P1"
    assert len(prefs.get_prefs("u1")["learned"]) == 1


def test_prefs_db_from_settings():
    """O path do DB vem de get_settings().prefs_db (env PREFS_DB do fixture)."""
    assert prefs._db_path() == get_settings().prefs_db


def test_fail_fast_in_production_without_secrets(monkeypatch):
    """N-1: produção (não-localhost) sem JWT_SECRET/CLOCKIFY_TOKEN_KEY → RuntimeError."""
    monkeypatch.setenv("PUBLIC_URL", "https://clockify.example.cloud")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("CLOCKIFY_TOKEN_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="secrets obrigatórios"):
        get_settings()


def test_local_keeps_insecure_defaults(monkeypatch):
    """Localhost mantém os defaults inseguros (os testes existentes dependem disso)."""
    monkeypatch.setenv("PUBLIC_URL", "http://localhost:8080")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.delenv("CLOCKIFY_TOKEN_KEY", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret == "dev-only-insecure-secret"
