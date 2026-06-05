"""Contexto do usuário derivado do token OAuth.

`request_context()` lê o access token da request atual (`get_access_token()`), pega a
identity dos claims (que É o dict inteiro `{uid,ck,ws,ics}`) e decifra `ck`/`ics` em
memória. As tools usam isto em vez de mexer nos claims na mão.
"""

from dataclasses import dataclass

from fastmcp.server.dependencies import get_access_token

from . import crypto
from .settings import get_settings


@dataclass(frozen=True)
class UserContext:
    api_key: str  # chave do Clockify em claro (só em memória)
    user_id: str
    workspace_id: str | None
    ics_url: str | None


def decode_identity(identity: dict) -> UserContext:
    """Decifra a identity (`ck`/`ics`) e monta o UserContext. `ics` pode ser None."""
    token_key = get_settings().token_key
    ics_blob = identity.get("ics")
    return UserContext(
        api_key=crypto.decrypt_key(token_key, identity["ck"]),
        user_id=identity["uid"],
        workspace_id=identity.get("ws"),
        ics_url=crypto.decrypt_key(token_key, ics_blob) if ics_blob else None,
    )


def request_context() -> UserContext:
    """UserContext da request atual. Levanta RuntimeError se não houver token."""
    token = get_access_token()
    if token is None:
        raise RuntimeError("sem token de acesso no contexto atual")
    return decode_identity(token.claims)
