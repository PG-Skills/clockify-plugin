"""Cliente Clockify async (httpx.AsyncClient). IO confiável: validação da chave,
busca DIRECIONADA por nome (projeto/tarefa/tag) e leitura/escrita de time-entries.

Diretriz mestre — simplicidade: NÃO lista o workspace inteiro (causava timeout). Cada
busca é por nome exato (`strict-name-search=true`), devolvendo só o match relevante.
"""

from typing import Any

import httpx

from .settings import get_settings

_PAGE_SIZE = 200
# busca exata por nome — evita varrer o workspace inteiro
_STRICT_NAME = "true"


def _headers(api_key: str) -> dict[str, str]:
    return {"X-Api-Key": api_key}


def _name_params(name: str) -> dict[str, str]:
    return {"name": name, "strict-name-search": _STRICT_NAME}


async def get_user(api_key: str) -> dict:
    """Valida a chave e retorna {id, name, email, workspace_id}. Levanta ValueError se a
    chave for inválida. `workspace_id` vem de defaultWorkspace (fallback activeWorkspace)."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.get("/user", headers=_headers(api_key))
    if resp.status_code == 401:
        raise ValueError("chave do Clockify inválida")
    resp.raise_for_status()
    d = resp.json()
    return {
        "id": d["id"],
        "name": d["name"],
        "email": d["email"],
        "workspace_id": d.get("defaultWorkspace") or d.get("activeWorkspace"),
    }


async def search_projects(api_key: str, workspace_id: str, name: str) -> list[dict]:
    """Projetos do workspace cujo nome casa exatamente com `name` (busca direcionada)."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.get(
            f"/workspaces/{workspace_id}/projects",
            headers=_headers(api_key),
            params=_name_params(name),
        )
    resp.raise_for_status()
    return resp.json()


async def tasks_in_project(
    api_key: str, workspace_id: str, project_id: str, name: str
) -> list[dict]:
    """Tarefas de `project_id` cujo nome casa exatamente com `name` (busca direcionada)."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.get(
            f"/workspaces/{workspace_id}/projects/{project_id}/tasks",
            headers=_headers(api_key),
            params=_name_params(name),
        )
    resp.raise_for_status()
    return resp.json()


async def search_tags(api_key: str, workspace_id: str, name: str) -> list[dict]:
    """Tags do workspace cujo nome casa exatamente com `name` (busca direcionada)."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.get(
            f"/workspaces/{workspace_id}/tags",
            headers=_headers(api_key),
            params=_name_params(name),
        )
    resp.raise_for_status()
    return resp.json()


async def entries(
    api_key: str, workspace_id: str, user_id: str, start: str, end: str
) -> list[dict]:
    """Time-entries crus do usuário na janela `[start, end]` (ISO UTC, ex.: `...Z`).

    GET paginado (`page`/`page-size`): percorre páginas até vir uma página incompleta.
    Cada entry traz `taskId`, `timeInterval.start`, etc.
    """
    base = get_settings().clockify_base
    path = f"/workspaces/{workspace_id}/user/{user_id}/time-entries"
    items: list[dict] = []
    page = 1
    async with httpx.AsyncClient(base_url=base, timeout=30.0) as client:
        while True:
            resp = await client.get(
                path,
                headers=_headers(api_key),
                params={
                    "start": start,
                    "end": end,
                    "page": page,
                    "page-size": _PAGE_SIZE,
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            items.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return items
            page += 1


async def create_entry(
    api_key: str, workspace_id: str, payload: dict[str, Any]
) -> dict:
    """Cria um time-entry (POST). `payload` já com IDs resolvidos e horários em UTC."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.post(
            f"/workspaces/{workspace_id}/time-entries",
            headers=_headers(api_key),
            json=payload,
        )
    resp.raise_for_status()
    return resp.json()
