"""Cliente Clockify síncrono (stdlib via http_json). Porta de server/clockify.py.

Diretriz mestre — simplicidade: NÃO lista o workspace inteiro (causava timeout). Cada
busca é por nome exato (`strict-name-search=true`), devolvendo só o match relevante."""

import http_json

BASE = "https://api.clockify.me/api/v1"
_PAGE_SIZE = 200
_STRICT_NAME = "true"


def _name_params(name: str) -> dict:
    return {"name": name, "strict-name-search": _STRICT_NAME}


def get_user(api_key: str) -> dict:
    """Valida a chave e retorna {id, name, email, workspace_id}. ValueError se inválida."""
    try:
        d = http_json.request_json("GET", f"{BASE}/user", api_key=api_key, timeout=10.0)
    except http_json.HttpError as e:
        if e.status in (401, 403):  # 401/403 = chave inválida ou sem permissão
            raise ValueError("chave do Clockify inválida") from e
        raise
    return {
        "id": d["id"],
        "name": d["name"],
        "email": d["email"],
        "workspace_id": d.get("defaultWorkspace") or d.get("activeWorkspace"),
    }


def search_projects(api_key: str, workspace_id: str, name: str) -> list[dict]:
    return http_json.request_json(
        "GET",
        f"{BASE}/workspaces/{workspace_id}/projects",
        api_key=api_key,
        params=_name_params(name),
        timeout=10.0,
    )


def tasks_in_project(
    api_key: str, workspace_id: str, project_id: str, name: str
) -> list[dict]:
    return http_json.request_json(
        "GET",
        f"{BASE}/workspaces/{workspace_id}/projects/{project_id}/tasks",
        api_key=api_key,
        params=_name_params(name),
        timeout=10.0,
    )


def search_tags(api_key: str, workspace_id: str, name: str) -> list[dict]:
    return http_json.request_json(
        "GET",
        f"{BASE}/workspaces/{workspace_id}/tags",
        api_key=api_key,
        params=_name_params(name),
        timeout=10.0,
    )


def entries(
    api_key: str, workspace_id: str, user_id: str, start: str, end: str
) -> list[dict]:
    """Time-entries crus na janela [start, end] (ISO UTC). GET paginado até página incompleta."""
    path = f"{BASE}/workspaces/{workspace_id}/user/{user_id}/time-entries"
    items: list[dict] = []
    page = 1
    while True:
        batch = http_json.request_json(
            "GET",
            path,
            api_key=api_key,
            params={"start": start, "end": end, "page": page, "page-size": _PAGE_SIZE},
        )
        items.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return items
        page += 1


def create_entry(api_key: str, workspace_id: str, payload: dict) -> dict:
    return http_json.request_json(
        "POST",
        f"{BASE}/workspaces/{workspace_id}/time-entries",
        api_key=api_key,
        body=payload,
        timeout=10.0,
    )
