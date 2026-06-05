"""Cliente mínimo do Clockify. A PoC só precisa de `get_user` (valida a chave)."""

import httpx

from .settings import get_settings


async def get_user(api_key: str) -> dict:
    """Valida a chave e retorna {id, name, email}. Levanta ValueError se a chave for inválida."""
    base = get_settings().clockify_base
    async with httpx.AsyncClient(base_url=base, timeout=10.0) as client:
        resp = await client.get("/user", headers={"X-Api-Key": api_key})
    if resp.status_code == 401:
        raise ValueError("chave do Clockify inválida")
    resp.raise_for_status()
    d = resp.json()
    return {"id": d["id"], "name": d["name"], "email": d["email"]}
