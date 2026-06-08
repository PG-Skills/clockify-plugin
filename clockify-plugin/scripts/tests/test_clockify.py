import pytest

import clockify
import http_json


def _patch(monkeypatch, handler):
    """handler(method, url, params, body) -> retorno de request_json."""

    def fake(method, url, *, api_key, params=None, body=None, timeout=30.0):
        return handler(method, url, params, body)

    monkeypatch.setattr(clockify.http_json, "request_json", fake)


def test_get_user_ok(monkeypatch):
    _patch(
        monkeypatch,
        lambda m, u, p, b: {
            "id": "u1",
            "name": "Ana",
            "email": "ana@pg.com",
            "defaultWorkspace": "ws1",
        },
    )
    out = clockify.get_user("KEY")
    assert out == {
        "id": "u1",
        "name": "Ana",
        "email": "ana@pg.com",
        "workspace_id": "ws1",
    }


def test_get_user_invalid_key_raises_valueerror(monkeypatch):
    for status in (401, 403):  # 401/403 = chave inválida ou sem permissão

        def handler(m, u, p, b, _s=status):
            raise http_json.HttpError(_s)

        _patch(monkeypatch, handler)
        with pytest.raises(ValueError):
            clockify.get_user("BAD")


def test_get_user_other_http_error_propagates(monkeypatch):
    def handler(m, u, p, b):
        raise http_json.HttpError(500)

    _patch(monkeypatch, handler)
    with pytest.raises(http_json.HttpError):
        clockify.get_user("KEY")


def test_search_projects_uses_strict_name(monkeypatch):
    seen = {}

    def handler(m, u, p, b):
        seen.update(p or {})
        return [{"id": "p1", "name": "Proj X"}]

    _patch(monkeypatch, handler)
    out = clockify.search_projects("K", "ws1", "Proj X")
    assert out[0]["id"] == "p1"
    assert seen == {"name": "Proj X", "strict-name-search": "true"}


def test_entries_paginates(monkeypatch):
    calls = {"n": 0}

    def handler(m, u, p, b):
        calls["n"] += 1
        # página 1 cheia (200), página 2 incompleta -> para
        return [{"id": f"e{calls['n']}"}] * 200 if calls["n"] == 1 else [{"id": "last"}]

    _patch(monkeypatch, handler)
    out = clockify.entries(
        "K", "ws1", "u1", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z"
    )
    assert calls["n"] == 2
    assert len(out) == 201


def test_entries_hydrated_adds_param(monkeypatch):
    seen = {}

    def handler(m, u, p, b):
        seen.update(p or {})
        return []  # vazio -> para na 1ª página

    _patch(monkeypatch, handler)
    clockify.entries("K", "ws1", "u1", "S", "E", hydrated=True)
    assert seen.get("hydrated") == "true"


def test_entries_not_hydrated_by_default(monkeypatch):
    seen = {}

    def handler(m, u, p, b):
        seen.update(p or {})
        return []

    _patch(monkeypatch, handler)
    clockify.entries("K", "ws1", "u1", "S", "E")
    assert "hydrated" not in seen


def test_create_entry_posts(monkeypatch):
    seen = {}

    def handler(m, u, p, b):
        seen["method"] = m
        seen["body"] = b
        return {"id": "e1"}

    _patch(monkeypatch, handler)
    out = clockify.create_entry("K", "ws1", {"description": "x"})
    assert (
        out == {"id": "e1"}
        and seen["method"] == "POST"
        and seen["body"]["description"] == "x"
    )
