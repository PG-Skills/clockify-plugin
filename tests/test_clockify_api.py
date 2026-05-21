from datetime import date
from zoneinfo import ZoneInfo

import httpx
import respx
from clockify_horas.clockify_api import ClockifyClient

BASE = "https://api.clockify.me/api/v1"
TZ = ZoneInfo("America/Sao_Paulo")


def _client() -> ClockifyClient:
    return ClockifyClient(api_key="key123", workspace_id="ws1")


@respx.mock
def test_get_user_id():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    assert _client().get_user_id() == "u1"


@respx.mock
def test_get_metadata_monta_indices():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(
            200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}]
        )
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    md = _client().get_metadata()
    assert md.user_id == "u1"
    assert md.projects["Procurement Garage"] == "p1"
    assert md.tasks[("p1", ".Célula de Inovação: Time IA")] == "t1"
    assert md.tags["Atividades Internas"] == "g1"


@respx.mock
def test_get_entries_for_date_usa_janela_utc_do_dia_local():
    route = respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[{"id": "e1"}])
    )
    entries = _client().get_entries_for_date("u1", date(2026, 1, 28), TZ)
    assert entries == [{"id": "e1"}]
    # dia local 28/01 em UTC-3 -> 28/01 03:00Z até 29/01 03:00Z
    sent = route.calls.last.request
    assert sent.url.params["start"] == "2026-01-28T03:00:00Z"
    assert sent.url.params["end"] == "2026-01-29T03:00:00Z"


@respx.mock
def test_get_metadata_pagina_ate_pagina_incompleta():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(return_value=httpx.Response(200, json=[]))
    md = _client().get_metadata()
    # 1 projeto (< page-size) encerra a paginação em uma página só
    assert list(md.projects) == ["Procurement Garage"]


@respx.mock
def test_create_entry_envia_payload():
    route = respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "new1"})
    )
    payload = {"start": "2026-01-28T16:00:00Z", "description": "x"}
    resp = _client().create_entry(payload)
    assert resp["id"] == "new1"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-Api-Key"] == "key123"
