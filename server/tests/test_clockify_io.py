"""IO async do Clockify (respx). Busca direcionada por nome — NÃO lista o workspace inteiro.

Cada busca passa `strict-name-search=true` + o `name` procurado. Espelha o estilo de
`test_core.py` (respx + async).
"""

import httpx
import respx

from clockify_mcp.clockify import (
    create_entry,
    entries,
    search_projects,
    search_tags,
    tasks_in_project,
)

BASE = "https://api.clockify.me/api/v1"
KEY = "key123"
WS = "ws1"


@respx.mock
async def test_search_projects_busca_direcionada():
    route = respx.get(f"{BASE}/workspaces/{WS}/projects").mock(
        return_value=httpx.Response(
            200, json=[{"id": "p1", "name": "Procurement Garage"}]
        )
    )
    out = await search_projects(KEY, WS, "Procurement Garage")
    assert out == [{"id": "p1", "name": "Procurement Garage"}]
    req = route.calls.last.request
    assert req.url.params["name"] == "Procurement Garage"
    assert req.url.params["strict-name-search"] == "true"
    assert req.headers["X-Api-Key"] == KEY


@respx.mock
async def test_tasks_in_project_busca_direcionada():
    route = respx.get(f"{BASE}/workspaces/{WS}/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": "Dev"}])
    )
    out = await tasks_in_project(KEY, WS, "p1", "Dev")
    assert out == [{"id": "t1", "name": "Dev"}]
    req = route.calls.last.request
    assert req.url.params["name"] == "Dev"
    assert req.url.params["strict-name-search"] == "true"


@respx.mock
async def test_search_tags_busca_direcionada():
    route = respx.get(f"{BASE}/workspaces/{WS}/tags").mock(
        return_value=httpx.Response(
            200, json=[{"id": "g1", "name": "Atividades Internas"}]
        )
    )
    out = await search_tags(KEY, WS, "Atividades Internas")
    assert out == [{"id": "g1", "name": "Atividades Internas"}]
    req = route.calls.last.request
    assert req.url.params["name"] == "Atividades Internas"
    assert req.url.params["strict-name-search"] == "true"


@respx.mock
async def test_entries_passa_janela_e_user():
    route = respx.get(f"{BASE}/workspaces/{WS}/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[{"id": "e1", "taskId": "t1"}])
    )
    out = await entries(KEY, WS, "u1", "2026-01-28T03:00:00Z", "2026-01-29T03:00:00Z")
    assert out == [{"id": "e1", "taskId": "t1"}]
    req = route.calls.last.request
    assert req.url.params["start"] == "2026-01-28T03:00:00Z"
    assert req.url.params["end"] == "2026-01-29T03:00:00Z"
    assert req.headers["X-Api-Key"] == KEY


@respx.mock
async def test_entries_pagina_ate_pagina_incompleta():
    """Página cheia (page-size) força segunda página; página curta encerra."""
    full = [{"id": f"e{i}"} for i in range(200)]
    route = respx.get(f"{BASE}/workspaces/{WS}/user/u1/time-entries")
    route.side_effect = [
        httpx.Response(200, json=full),
        httpx.Response(200, json=[{"id": "tail"}]),
    ]
    out = await entries(KEY, WS, "u1", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z")
    assert len(out) == 201
    assert out[-1] == {"id": "tail"}
    assert route.call_count == 2
    # 2ª chamada pediu a página seguinte
    assert route.calls[1].request.url.params["page"] == "2"


@respx.mock
async def test_create_entry_envia_payload():
    route = respx.post(f"{BASE}/workspaces/{WS}/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "new1"})
    )
    payload = {"start": "2026-01-28T16:00:00Z", "description": "x"}
    out = await create_entry(KEY, WS, payload)
    assert out == {"id": "new1"}
    req = route.calls.last.request
    assert req.headers["X-Api-Key"] == KEY
