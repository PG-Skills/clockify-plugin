"""Prova empírica do design stateless: a chave do Clockify sobrevive ao ciclo
authorize → code → access → refresh, sem nunca ser guardada nem aparecer em texto.
"""

import json

import jwt
import pytest
from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from prototype import StatelessClockifyOAuth, mint_authorization_code, SIGN, ISSUER

CLOCKIFY_KEY = (
    "Yjk2ZmZ-clockify-secret-AAA"  # a chave real que NUNCA pode vazar em texto
)
UID = "user-123"


def _client() -> OAuthClientInformationFull:
    return OAuthClientInformationFull(
        client_id="cowork-client",
        redirect_uris=[AnyUrl("https://claude.ai/api/mcp/auth_callback")],
        token_endpoint_auth_method="none",
    )


def _params() -> AuthorizationParams:
    return AuthorizationParams(
        state="xyz",
        scopes=["clockify"],
        code_challenge="abc123",
        redirect_uri=AnyUrl("https://claude.ai/api/mcp/auth_callback"),
        redirect_uri_provided_explicitly=True,
        resource="https://clockify.example/mcp",
    )


@pytest.mark.asyncio
async def test_key_survives_full_oauth_cycle_stateless():
    p = StatelessClockifyOAuth()
    client = _client()
    await p.register_client(client)

    # 1) A página /connect validou a chave (uid descoberto via Clockify) e emitiu o code.
    code_str = mint_authorization_code(UID, CLOCKIFY_KEY, _params(), client.client_id)

    # 2) /token: troca o code por access + refresh.
    code = await p.load_authorization_code(client, code_str)
    assert code is not None
    tok = await p.exchange_authorization_code(client, code)
    assert tok.access_token and tok.refresh_token

    # 3) verify do access → a tool consegue recuperar a chave (descriptografando ck).
    access = await p.verify_token(tok.access_token)
    assert access is not None
    from prototype import dec

    assert dec(access.claims["ck"]) == CLOCKIFY_KEY
    assert access.claims["uid"] == UID

    # 4) A chave NUNCA aparece em texto no token (claims só têm o blob cifrado).
    raw = jwt.decode(tok.access_token, SIGN, algorithms=["HS256"], issuer=ISSUER)
    assert CLOCKIFY_KEY not in json.dumps(raw)
    assert CLOCKIFY_KEY not in tok.access_token
    assert CLOCKIFY_KEY not in tok.refresh_token

    # 5) C3: REFRESH stateless — o Cowork renova o token expirado SEM recoletar a chave.
    rt = await p.load_refresh_token(client, tok.refresh_token)
    assert rt is not None
    tok2 = await p.exchange_refresh_token(client, rt, scopes=["clockify"])
    access2 = await p.verify_token(tok2.access_token)
    assert (
        dec(access2.claims["ck"]) == CLOCKIFY_KEY
    )  # a chave voltou, vinda do refresh token
    assert tok2.access_token != tok.access_token  # token novo de verdade


@pytest.mark.asyncio
async def test_tampered_token_is_rejected():
    p = StatelessClockifyOAuth()
    bad = "eyJ0eXAiOiJKV1QifQ.tampered.signature"
    assert await p.verify_token(bad) is None
