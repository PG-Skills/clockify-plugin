"""Resolução direcionada (projeto+tarefa+tag) e add_entries com anti-duplicata.

O endpoint de tasks do Clockify EXIGE projectId — não há busca global de tarefa. Por
isso `resolve_activity` sem `project` devolve AMBIGUO ("projeto necessário"); a skill
conversacional fornece o `project` (atividade aprendida/padrão) antes de chamar.

Mocka as funções de IO de `clockify_mcp.clockify` (monkeypatch) — sem rede. Retornos
estruturados são idioma-neutro: só dados, NUNCA frase pronta pro usuário.
"""

import clockify_mcp.clockify as cl
from clockify_mcp.resolve import add_entries, resolve_activity

KEY = "key123"
WS = "ws1"
UID = "u1"


def _fake_search(mapping: dict[str, list[dict]]):
    async def _f(api_key, workspace_id, name):
        return mapping.get(name, [])

    return _f


def _fake_tasks(mapping: dict[tuple[str, str], list[dict]]):
    async def _f(api_key, workspace_id, project_id, name):
        return mapping.get((project_id, name), [])

    return _f


# --- resolve_activity ------------------------------------------------------


async def test_resolve_activity_projeto_ambiguo(monkeypatch):
    monkeypatch.setattr(
        cl,
        "search_projects",
        _fake_search(
            {
                "Cliente X": [
                    {"id": "p1", "name": "Cliente X"},
                    {"id": "p2", "name": "Cliente X"},
                ]
            }
        ),
    )
    out = await resolve_activity(KEY, WS, name="Dev", project="Cliente X")
    assert out["status"] == "AMBIGUO"
    assert len(out["candidatos"]) == 2
    # idioma-neutro: nenhuma frase pronta — só dados
    assert "motivo" in out


async def test_resolve_activity_com_projeto_e_um_match_e_ok(monkeypatch):
    """Guard W-1: projeto fornecido + 1 match de projeto e 1 de tarefa => OK, sem AMBIGUO."""
    monkeypatch.setattr(
        cl,
        "search_projects",
        _fake_search({"Cliente X": [{"id": "p1", "name": "Cliente X"}]}),
    )
    monkeypatch.setattr(
        cl,
        "tasks_in_project",
        _fake_tasks({("p1", "Dev"): [{"id": "t1", "name": "Dev"}]}),
    )
    out = await resolve_activity(KEY, WS, name="Dev", project="Cliente X")
    assert out["status"] == "OK"
    assert out["project_id"] == "p1"
    assert out["task_id"] == "t1"
    assert out["tag_ids"] == []


async def test_resolve_activity_sem_projeto_pede_projeto(monkeypatch):
    out = await resolve_activity(KEY, WS, name="Dev", project=None)
    assert out["status"] == "AMBIGUO"
    assert "projeto" in out["motivo"]


async def test_resolve_activity_tarefa_nao_encontrada(monkeypatch):
    monkeypatch.setattr(
        cl,
        "search_projects",
        _fake_search({"Cliente X": [{"id": "p1", "name": "Cliente X"}]}),
    )
    monkeypatch.setattr(cl, "tasks_in_project", _fake_tasks({}))
    out = await resolve_activity(KEY, WS, name="Inexistente", project="Cliente X")
    assert out["status"] == "NAO_ENCONTRADO"


async def test_resolve_activity_resolve_tag(monkeypatch):
    monkeypatch.setattr(
        cl,
        "search_projects",
        _fake_search({"Cliente X": [{"id": "p1", "name": "Cliente X"}]}),
    )
    monkeypatch.setattr(
        cl,
        "tasks_in_project",
        _fake_tasks({("p1", "Dev"): [{"id": "t1", "name": "Dev"}]}),
    )
    monkeypatch.setattr(
        cl, "search_tags", _fake_search({"Interna": [{"id": "g1", "name": "Interna"}]})
    )
    out = await resolve_activity(
        KEY, WS, name="Dev", project="Cliente X", tag="Interna"
    )
    assert out["status"] == "OK"
    assert out["tag_ids"] == ["g1"]


# --- add_entries -----------------------------------------------------------


def _ok_resolver(monkeypatch, projects, tasks):
    monkeypatch.setattr(cl, "search_projects", _fake_search(projects))
    monkeypatch.setattr(cl, "tasks_in_project", _fake_tasks(tasks))


async def test_add_entries_para_no_primeiro_erro(monkeypatch):
    """1º item resolve e grava; 2º item falha na resolução => para, gravados==1, falhou_em==1."""
    _ok_resolver(
        monkeypatch,
        {"Cliente X": [{"id": "p1", "name": "Cliente X"}]},
        {("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )

    async def _no_entries(api_key, workspace_id, user_id, start, end):
        return []

    created: list[dict] = []

    async def _create(api_key, workspace_id, payload):
        created.append(payload)
        return {"id": f"e{len(created)}"}

    monkeypatch.setattr(cl, "entries", _no_entries)
    monkeypatch.setattr(cl, "create_entry", _create)

    items = [
        {
            "description": "ok",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Cliente X",
        },
        {
            "description": "falha",
            "date": "2026-01-28",
            "start": "10:00",
            "end": "11:00",
            "task": "Inexistente",
            "project": "Cliente X",
        },
    ]
    out = await add_entries(KEY, WS, UID, items)
    assert out["gravados"] == 1
    assert out["total"] == 2
    assert out["falhou_em"] == 1
    assert out["motivo"] is not None
    assert len(created) == 1  # parou antes de gravar o 2º


async def test_add_entries_pula_duplicata(monkeypatch):
    """Item cujo (data local, taskId) já existe nas entries => pulado, sem create_entry."""
    _ok_resolver(
        monkeypatch,
        {"Cliente X": [{"id": "p1", "name": "Cliente X"}]},
        {("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )

    async def _entries(api_key, workspace_id, user_id, start, end):
        # entry já existente: taskId t1 em 2026-01-28 (local). 12:00Z = 09:00 local (UTC-3).
        return [
            {
                "id": "old",
                "taskId": "t1",
                "timeInterval": {"start": "2026-01-28T12:00:00Z"},
            }
        ]

    created: list[dict] = []

    async def _create(api_key, workspace_id, payload):
        created.append(payload)
        return {"id": f"e{len(created)}"}

    monkeypatch.setattr(cl, "entries", _entries)
    monkeypatch.setattr(cl, "create_entry", _create)

    items = [
        {
            "description": "dup",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Cliente X",
        },
    ]
    out = await add_entries(KEY, WS, UID, items)
    assert out["pulados_duplicata"] >= 1
    assert out["gravados"] == 0
    assert out["falhou_em"] is None
    assert created == []  # não chamou create_entry para a duplicata


async def test_add_entries_pula_duplicata_em_horario_anterior(monkeypatch):
    """Regressão: duplicata pré-existente ANTES do 1º item do lote ainda é pulada.

    Bug: a janela de leitura usava min(starts)..max(ends) dos HORÁRIOS do lote. Uma
    entry da mesma tarefa no mesmo dia mas em horário anterior (08:00) caía fora da
    janela 09:00–10:00 e era duplicada. A correção lê o DIA LOCAL inteiro.
    """
    _ok_resolver(
        monkeypatch,
        {"Cliente X": [{"id": "p1", "name": "Cliente X"}]},
        {("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )

    # entry pré-existente às 08:00 local (11:00Z em UTC-3) — antes do 1º item do lote.
    pre = {
        "id": "old",
        "taskId": "t1",
        "timeInterval": {"start": "2026-01-28T11:00:00Z"},
    }

    async def _entries(api_key, workspace_id, user_id, start, end):
        # Mock fiel ao IO real: só devolve a entry se a janela consultada a cobrir.
        return [pre] if start <= "2026-01-28T11:00:00Z" < end else []

    created: list[dict] = []

    async def _create(api_key, workspace_id, payload):
        created.append(payload)
        return {"id": f"e{len(created)}"}

    monkeypatch.setattr(cl, "entries", _entries)
    monkeypatch.setattr(cl, "create_entry", _create)

    items = [
        {
            "description": "dup",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Cliente X",
        },
    ]
    out = await add_entries(KEY, WS, UID, items)
    assert out["pulados_duplicata"] >= 1
    assert out["gravados"] == 0
    assert created == []  # não duplicou a entry das 08:00


async def test_add_entries_grava_payload_com_ids_e_utc(monkeypatch):
    """Sucesso simples: payload tem IDs resolvidos e start/end em UTC (Z)."""
    _ok_resolver(
        monkeypatch,
        {"Cliente X": [{"id": "p1", "name": "Cliente X"}]},
        {("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )

    async def _no_entries(api_key, workspace_id, user_id, start, end):
        return []

    created: list[dict] = []

    async def _create(api_key, workspace_id, payload):
        created.append(payload)
        return {"id": "new"}

    monkeypatch.setattr(cl, "entries", _no_entries)
    monkeypatch.setattr(cl, "create_entry", _create)

    items = [
        {
            "description": "Dev",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Cliente X",
            "billable": True,
        },
    ]
    out = await add_entries(KEY, WS, UID, items)
    assert out["gravados"] == 1
    p = created[0]
    assert p["projectId"] == "p1"
    assert p["taskId"] == "t1"
    assert p["start"] == "2026-01-28T12:00:00Z"  # 09:00 local (UTC-3) -> 12:00Z
    assert p["end"] == "2026-01-28T13:00:00Z"
    assert p["billable"] is True
