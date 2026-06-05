"""Integração: monta o FastMCP server com o provider OAuth stateless + a tool whoami
que lê a chave do token (get_access_token().claims) — o jeito idiomático (corrige C1).
"""

import httpx
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from prototype import StatelessClockifyOAuth, dec

provider = StatelessClockifyOAuth()
mcp = FastMCP(name="clockify-mcp", auth=provider)


@mcp.tool
async def whoami() -> str:
    """Confirma a conexão: devolve o nome da conta do Clockify."""
    token = get_access_token()
    api_key = dec(token.claims["ck"])  # descriptografa em memória, por request
    async with httpx.AsyncClient(
        base_url="https://api.clockify.me/api/v1", timeout=10
    ) as c:
        r = await c.get("/user", headers={"X-Api-Key": api_key})
    if r.status_code == 401:
        raise ValueError("chave do Clockify inválida")
    r.raise_for_status()
    u = r.json()
    return f"Conectado como {u['name']} ({u['email']})."
