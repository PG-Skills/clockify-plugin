import io
import json

import cli
import clockify
import config
import prefs as prefs_mod
import resolve as resolve_mod


def _seed_creds(monkeypatch, tmp_path, **over):
    """Pré-popula credentials.json COMPLETO (api_key+workspace_id+user_id) para que o
    caminho quente NÃO chame get_user (rede). Reproduz o estado pós-whoami."""
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    base = {"api_key": "KEY", "ics_url": None, "workspace_id": "ws1", "user_id": "u1"}
    base.update(over)
    config.save_credentials(**base)


def _run(argv):
    buf = io.StringIO()
    code = cli.main(argv, stdout=buf)
    text = buf.getvalue()
    return code, (json.loads(text) if text.strip() else None)


def test_whoami_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["whoami"])
    assert code == 3 and out == {"error": "NO_KEY"}


def test_whoami_ok_caches_account(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="KEY", ics_url=None, workspace_id=None, user_id=None
    )
    monkeypatch.setattr(
        clockify,
        "get_user",
        lambda k: {
            "id": "u1",
            "name": "Ana",
            "email": "a@pg.com",
            "workspace_id": "ws1",
        },
    )
    code, out = _run(["whoami"])
    assert code == 0 and out["name"] == "Ana"
    creds = config.load_credentials()
    assert creds["workspace_id"] == "ws1" and creds["user_id"] == "u1"  # cache de conta


def test_whoami_invalid_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="BAD", ics_url=None, workspace_id=None)

    def boom(k):
        raise ValueError("inválida")

    monkeypatch.setattr(clockify, "get_user", boom)
    code, out = _run(["whoami"])
    assert code == 4 and out == {"error": "INVALID_KEY"}


def test_business_days(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["business-days", "--start", "2026-01-30", "--end", "2026-02-02"])
    assert code == 0 and out == {"days": ["2026-01-30", "2026-02-02"]}


def test_entries_uses_cache_no_network(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)

    def boom(*a, **k):  # get_user NÃO pode ser chamado — cache completo
        raise AssertionError("get_user não deveria ser chamado")

    monkeypatch.setattr(clockify, "get_user", boom)
    monkeypatch.setattr(clockify, "entries", lambda key, ws, uid, s, e: [{"id": "e1"}])
    code, out = _run(["entries", "--date", "2026-01-28"])
    assert code == 0 and out == {"entries": [{"id": "e1"}]}


def test_add_dry_run_does_not_write(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    called = {"n": 0}
    monkeypatch.setattr(
        resolve_mod, "add_entries", lambda *a, **k: called.__setitem__("n", 1)
    )
    payload = json.dumps(
        [
            {
                "date": "2026-01-28",
                "start": "9:00",
                "end": "10:00",
                "task": "Dev",
                "project": "Proj X",
            }
        ]
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert code == 0 and out["dry_run"] is True and called["n"] == 0


def test_add_real_calls_add_entries_no_network(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise AssertionError("get_user não deveria ser chamado — cache completo")

    monkeypatch.setattr(clockify, "get_user", boom)
    monkeypatch.setattr(
        resolve_mod,
        "add_entries",
        lambda key, ws, uid, items: {
            "gravados": 1,
            "total": 1,
            "pulados_duplicata": 0,
            "falhou_em": None,
            "motivo": None,
        },
    )
    payload = json.dumps(
        [
            {
                "date": "2026-01-28",
                "start": "9:00",
                "end": "10:00",
                "task": "Dev",
                "project": "Proj X",
            }
        ]
    )
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-"])
    assert code == 0 and out["gravados"] == 1


def test_add_rejects_malformed_items(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    payload = json.dumps([{"date": "2026-01-28", "task": "Dev"}])  # falta start/end
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert code == 2 and out["error"] == "INVALID_ITEMS" and out["missing_at"] == [0]


def test_prefs_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs_mod.learn("x", project="P", task=None, tag=None, billable=None)
    code, out = _run(["prefs", "reset"])
    assert code == 0 and out == {"ok": True}
    assert prefs_mod.get_prefs()["learned"] == []


def test_entries_invalid_key_incomplete_cache(monkeypatch, tmp_path):
    # cache incompleto (sem ws/uid) + chave ruim → INVALID_KEY estruturado, não traceback
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="BAD", ics_url=None, workspace_id=None, user_id=None
    )

    def boom(k):
        raise ValueError("inválida")

    monkeypatch.setattr(clockify, "get_user", boom)
    code, out = _run(["entries", "--date", "2026-01-28"])
    assert code == 4 and out == {"error": "INVALID_KEY"}


def test_add_rejects_non_list(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "sys.stdin", io.StringIO('{"date":"2026-01-28"}')
    )  # objeto, não lista
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert (
        code == 2
        and out["error"] == "INVALID_ITEMS"
        and out["reason"] == "esperava_lista"
    )
