"""Tools MCP idioma-neutras: devolvem DADOS (dict/list, ISO, ids, números), NUNCA
frases pro usuário (quem verbaliza é a skill conversacional na língua do usuário).

Cada teste mocka `request_context` (devolve um UserContext de teste) e as funções de
IO (clockify/ics/prefs/resolve), e assere a ESTRUTURA do retorno. Também trava que as
tools estão REGISTRADAS no `mcp` e que `whoami` virou dict (não string-frase)."""

from datetime import datetime
from zoneinfo import ZoneInfo


from clockify_mcp import tools as tools_mod
from clockify_mcp.app import mcp
from clockify_mcp.context import UserContext

_TZ = ZoneInfo("America/Sao_Paulo")

EXPECTED_TOOLS = {
    "whoami",
    "agenda",
    "entries",
    "business_days",
    "resolve_activity",
    "add_entries",
    "get_prefs",
    "learn_activity",
    "set_default",
}


def _ctx(ics_url: str | None = None) -> UserContext:
    return UserContext(
        api_key="KEY",
        user_id="u1",
        workspace_id="ws1",
        ics_url=ics_url,
    )


def _patch_ctx(monkeypatch, ctx: UserContext) -> None:
    """request_context() é importado em tools.py — substitui lá."""
    monkeypatch.setattr(tools_mod, "request_context", lambda: ctx)


# --- registro ---------------------------------------------------------------


async def test_all_tools_registered():
    names = {t.name for t in await mcp.list_tools()}
    assert EXPECTED_TOOLS <= names


async def _call(_tool_name: str, **kwargs):
    """Chama a função subjacente da tool registrada (idioma-neutro: devolve dados)."""
    tool = await mcp.get_tool(_tool_name)
    assert tool is not None
    return await tool.fn(**kwargs)  # pyright: ignore[reportAttributeAccessIssue]


# --- whoami (virou dict) ----------------------------------------------------


async def test_whoami_returns_dict_not_string(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())

    async def _get_user(api_key):
        assert api_key == "KEY"
        return {"id": "u1", "name": "Ana", "email": "ana@pg.com", "workspace_id": "ws1"}

    monkeypatch.setattr(tools_mod, "get_user", _get_user)
    out = await _call("whoami")
    assert out == {"name": "Ana", "email": "ana@pg.com"}
    assert not isinstance(out, str)


# --- agenda -----------------------------------------------------------------


async def test_agenda_sem_ics_devolve_vazio(monkeypatch):
    _patch_ctx(monkeypatch, _ctx(ics_url=None))
    out = await _call("agenda", date="2026-01-28")
    assert out == {"ics": False, "eventos": []}


async def test_agenda_com_ics_devolve_eventos_iso(monkeypatch):
    _patch_ctx(monkeypatch, _ctx(ics_url="https://outlook/cal.ics"))

    async def _fetch(url):
        assert url == "https://outlook/cal.ics"
        return "ICS-TEXT"

    def _events(ics_text, target_date, tz=None):
        assert ics_text == "ICS-TEXT"
        return [
            {
                "title": "Reunião",
                "start": datetime(2026, 1, 28, 13, 0, tzinfo=_TZ),
                "end": datetime(2026, 1, 28, 14, 0, tzinfo=_TZ),
            }
        ]

    monkeypatch.setattr(tools_mod, "fetch_ics", _fetch)
    monkeypatch.setattr(tools_mod, "events_for_day", _events)
    out = await _call("agenda", date="2026-01-28")
    assert out["ics"] is True
    assert len(out["eventos"]) == 1
    ev = out["eventos"][0]
    assert ev["title"] == "Reunião"
    # datas serializadas como ISO (string), não datetime cru
    assert ev["start"] == "2026-01-28T13:00:00-03:00"
    assert ev["end"] == "2026-01-28T14:00:00-03:00"


# --- entries ----------------------------------------------------------------


async def test_entries_um_dia(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    captured = {}

    async def _entries(api_key, ws, uid, start, end):
        captured["args"] = (api_key, ws, uid, start, end)
        return [{"id": "e1", "taskId": "t1", "timeInterval": {"start": "x"}}]

    monkeypatch.setattr(tools_mod, "cl_entries", _entries)
    out = await _call("entries", start="2026-01-28")
    assert isinstance(out, list)
    assert out[0]["taskId"] == "t1"
    api_key, ws, uid, start, end = captured["args"]
    assert (api_key, ws, uid) == ("KEY", "ws1", "u1")
    # janela de UM dia em UTC (09:00 local -> ...Z)
    assert start.endswith("Z") and end.endswith("Z")


async def test_entries_intervalo(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    captured = {}

    async def _entries(api_key, ws, uid, start, end):
        captured["win"] = (start, end)
        return []

    monkeypatch.setattr(tools_mod, "cl_entries", _entries)
    out = await _call("entries", start="2026-01-01", end="2026-01-31")
    assert out == []
    start, end = captured["win"]
    assert start.endswith("Z") and end.endswith("Z")
    # intervalo cobre mais que um dia
    assert start < end


# --- business_days ----------------------------------------------------------


async def test_business_days_lista_iso(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    out = await _call("business_days", start="2026-01-26", end="2026-01-30")
    # seg 26 ... sex 30 = 5 dias úteis, todas strings ISO
    assert out == [
        "2026-01-26",
        "2026-01-27",
        "2026-01-28",
        "2026-01-29",
        "2026-01-30",
    ]
    assert all(isinstance(d, str) for d in out)


# --- resolve_activity -------------------------------------------------------


async def test_resolve_activity_repassa_dict(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    sentinel = {"status": "OK", "project_id": "p1", "task_id": "t1", "tag_ids": []}

    async def _resolve(api_key, ws, *, name, project=None, tag=None):
        assert (api_key, ws) == ("KEY", "ws1")
        assert name == "Dev" and project == "Cliente X"
        return sentinel

    monkeypatch.setattr(tools_mod, "resolve_activity_io", _resolve)
    out = await _call("resolve_activity", name="Dev", project="Cliente X")
    assert out == sentinel


# --- add_entries ------------------------------------------------------------


async def test_add_entries_repassa_dict(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    sentinel = {
        "gravados": 1,
        "total": 1,
        "pulados_duplicata": 0,
        "falhou_em": None,
        "motivo": None,
    }
    captured = {}

    async def _add(api_key, ws, uid, items):
        captured["args"] = (api_key, ws, uid, items)
        return sentinel

    monkeypatch.setattr(tools_mod, "add_entries_io", _add)
    items = [
        {
            "description": "Dev",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Cliente X",
        }
    ]
    out = await _call("add_entries", items=items)
    assert out == sentinel
    assert captured["args"] == ("KEY", "ws1", "u1", items)


# --- prefs ------------------------------------------------------------------


async def test_get_prefs_usa_user_id_do_contexto(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())

    def _get(uid):
        assert uid == "u1"
        return {"default": None, "learned": []}

    monkeypatch.setattr(tools_mod, "prefs_get", _get)
    out = await _call("get_prefs")
    assert out == {"default": None, "learned": []}


async def test_learn_activity_chama_prefs_learn(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    captured = {}

    def _learn(uid, match, *, project=None, task=None, tag=None, billable=None):
        captured["call"] = (uid, match, project, task, tag, billable)

    monkeypatch.setattr(tools_mod, "prefs_learn", _learn)
    out = await _call(
        "learn_activity", match="Reunião", project="P", task="T", billable=True
    )
    assert captured["call"] == ("u1", "Reunião", "P", "T", None, True)
    # idioma-neutro: devolve um ack mínimo de dados, nunca frase
    assert isinstance(out, dict)
    assert not isinstance(out, str)


async def test_set_default_chama_prefs_set_default(monkeypatch):
    _patch_ctx(monkeypatch, _ctx())
    captured = {}

    def _set(
        uid, *, project=None, task=None, tag=None, billable=None, daily_target=None
    ):
        captured["call"] = (uid, project, task, tag, billable, daily_target)

    monkeypatch.setattr(tools_mod, "prefs_set_default", _set)
    out = await _call("set_default", project="P", task="T", daily_target=8.0)
    assert captured["call"] == ("u1", "P", "T", None, None, 8.0)
    assert isinstance(out, dict)
    assert not isinstance(out, str)
