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


def test_add_from_file_path_dry_run(monkeypatch, tmp_path):
    # exercita o branch --json <arquivo> (Path.read_text) — regressão do import faltante
    _seed_creds(monkeypatch, tmp_path)
    f = tmp_path / "items.json"
    f.write_text(
        '[{"date":"2026-01-28","start":"9:00","end":"10:00","task":"Dev","project":"X"}]',
        encoding="utf-8",
    )
    code, out = _run(["add", "--json", str(f), "--dry-run"])
    assert code == 0 and out["dry_run"] is True


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


def test_business_days_invalid_range(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["business-days", "--start", "2026-02-02", "--end", "2026-01-30"])
    assert code == 2 and out["error"] == "INVALID_INPUT"


def test_agenda_no_ics_configured(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)  # sem ics_url
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 0 and out == {"ics": False, "eventos": []}


def test_agenda_with_ics(monkeypatch, tmp_path):
    import config
    import ics as ics_mod

    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="KEY", ics_url="https://x/y.ics", workspace_id="ws1", user_id="u1"
    )
    monkeypatch.setattr(ics_mod, "fetch_ics", lambda url: "ICSTEXT")
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("America/Sao_Paulo")
    monkeypatch.setattr(
        ics_mod,
        "events_for_day",
        lambda txt, d, z: [
            {
                "title": "Daily",
                "start": datetime(2026, 1, 28, 9, 0, tzinfo=tz),
                "end": datetime(2026, 1, 28, 9, 30, tzinfo=tz),
            }
        ],
    )
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 0 and out["ics"] is True
    assert out["eventos"][0]["title"] == "Daily"
    assert out["eventos"][0]["start"].startswith("2026-01-28T09:00")


def test_agenda_ics_error(monkeypatch, tmp_path):
    import config
    import ics as ics_mod

    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="KEY", ics_url="https://x/y.ics", workspace_id="ws1", user_id="u1"
    )

    def boom(url):
        raise ValueError("ics_url precisa usar https://")

    monkeypatch.setattr(ics_mod, "fetch_ics", boom)
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 5 and out["error"] == "ICS_ERROR"


def test_report_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["report", "--month", "2026-06"])
    assert code == 3 and out == {"error": "NO_KEY"}


def test_report_daily(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    monkeypatch.setattr(
        clockify, "get_user", lambda k: (_ for _ in ()).throw(AssertionError("cache"))
    )
    seen = {}

    def fake_entries(key, ws, uid, s, e, hydrated=False):
        seen["hydrated"] = hydrated
        return [
            {
                "timeInterval": {
                    "start": "2026-06-01T12:00:00Z",
                    "end": "2026-06-01T13:00:00Z",
                },
                "project": {"id": "p1", "name": "San Pablo"},
            },
        ]

    monkeypatch.setattr(clockify, "entries", fake_entries)
    code, out = _run(["report", "--month", "2026-06"])
    assert code == 0 and out["mode"] == "daily" and out["month"] == "2026-06"
    assert out["total_hours"] == 1.0 and out["days"] == [
        {"date": "2026-06-01", "hours": 1.0}
    ]
    assert seen["hydrated"] is True  # report pede entries hidratados (nome do projeto)
    assert out["summary"]["days_logged"] == 1
    assert out["summary"]["max_day"]["hours"] == 1.0
    assert out["by_project"] == [{"project": "San Pablo", "hours": 1.0}]
    assert isinstance(
        out["gaps"], list
    )  # lacunas dependem de "hoje" (não-determinístico aqui)


def test_report_monthly(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)

    def fake_entries(key, ws, uid, s, e, hydrated=False):
        return [
            {
                "timeInterval": {
                    "start": "2026-01-15T12:00:00Z",
                    "end": "2026-01-15T20:00:00Z",
                },
                "project": {"id": "p1", "name": "San Pablo"},
            },
        ]

    monkeypatch.setattr(clockify, "entries", fake_entries)
    code, out = _run(["report", "--start", "2026-01", "--end", "2026-03"])
    assert code == 0 and out["mode"] == "monthly"
    assert out["total_hours"] == 8.0 and out["months"] == [
        {"month": "2026-01", "hours": 8.0}
    ]
    assert out["summary"]["months_logged"] == 1
    assert out["by_project"] == [{"project": "San Pablo", "hours": 8.0}]
    assert "gaps" not in out  # lacunas só no modo diário


def test_report_range_over_12_months(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report", "--start", "2025-01", "--end", "2026-02"])  # 14 meses
    assert (
        code == 2
        and out["error"] == "INVALID_INPUT"
        and out["reason"] == "max_12_meses"
    )


def test_report_requires_mode(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report"])
    assert code == 2 and out["error"] == "INVALID_INPUT"


def test_report_malformed_month(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report", "--month", "2026/06"])
    assert code == 2 and out["error"] == "INVALID_INPUT"


def test_setup_status_configured(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="K", ics_url="https://x/y.ics", workspace_id="w", user_id="u"
    )

    def boom(*a, **k):  # setup-status é LOCAL: não pode tocar a rede
        raise AssertionError("setup-status não deve chamar a rede")

    monkeypatch.setattr(clockify, "get_user", boom)
    code, out = _run(["setup-status"])
    assert code == 0
    assert out == {
        "has_key": True,
        "has_ics": True,
        "configured": True,
        "dir": str(tmp_path),
    }


def test_setup_status_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["setup-status"])
    assert code == 0
    assert out == {
        "has_key": False,
        "has_ics": False,
        "configured": False,
        "dir": str(tmp_path),
    }


def test_setup_status_key_without_ics_incomplete(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="K", ics_url=None, workspace_id="w", user_id="u")
    code, out = _run(["setup-status"])
    assert code == 0
    assert out["has_key"] is True and out["has_ics"] is False
    assert out["configured"] is False and out["dir"] == str(tmp_path)


def test_whoami_network_blocked(monkeypatch, tmp_path):
    # proxy do sandbox recusa a saída (URLError) → NETWORK_BLOCKED, nunca traceback
    import urllib.error

    import http_json

    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(
        api_key="KEY", ics_url=None, workspace_id=None, user_id=None
    )

    def boom(*a, **k):
        raise urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))

    monkeypatch.setattr(http_json, "request_json", boom)
    code, out = _run(["whoami"])
    assert code == 5 and out["error"] == "NETWORK_BLOCKED"
    assert "403" in out["reason"]


def test_entries_network_blocked(monkeypatch, tmp_path):
    import urllib.error

    _seed_creds(monkeypatch, tmp_path)

    def boom(*a, **k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(clockify, "entries", boom)
    code, out = _run(["entries", "--date", "2026-01-28"])
    assert code == 5 and out["error"] == "NETWORK_BLOCKED"


def test_agenda_network_blocked_is_not_ics_error(monkeypatch, tmp_path):
    # bloqueio de rede ao buscar o ICS NÃO pode virar ICS_ERROR ("seu link não funciona")
    import urllib.error

    import ics as ics_mod

    _seed_creds(monkeypatch, tmp_path, ics_url="https://outlook.example/cal.ics")

    def boom(url):
        raise urllib.error.URLError(OSError("Tunnel connection failed: 403 Forbidden"))

    monkeypatch.setattr(ics_mod, "fetch_ics", boom)
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 5 and out["error"] == "NETWORK_BLOCKED"


def test_agenda_dead_link_still_ics_error(monkeypatch, tmp_path):
    # HTTPError (link morto/404) continua ICS_ERROR — só bloqueio vira NETWORK_BLOCKED
    import urllib.error

    import ics as ics_mod

    _seed_creds(monkeypatch, tmp_path, ics_url="https://outlook.example/cal.ics")

    def boom(url):
        raise urllib.error.HTTPError(
            "https://outlook.example/cal.ics", 404, "Not Found", None, None
        )

    monkeypatch.setattr(ics_mod, "fetch_ics", boom)
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 5 and out["error"] == "ICS_ERROR"
