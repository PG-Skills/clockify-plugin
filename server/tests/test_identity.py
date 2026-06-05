"""Identidade ÚNICA no token OAuth: o dict `identity={uid,ck,ws,ics}` viaja inteiro
pela cadeia (code -> access/refresh -> refresh) sem cópia campo-a-campo. Esses testes
travam a regra que mata a classe de bug "claim some no refresh" (ws/ics sobrevivem)."""

import json

import pytest
from mcp.shared.auth import OAuthClientInformationFull
from pydantic import AnyUrl

from clockify_mcp import auth, context, crypto
from clockify_mcp.settings import get_settings

CLOCKIFY_KEY = "Yjk2-clockify-secret-NUNCA-EM-TEXTO"
ICS_URL = "https://outlook.example/owa/calendar/abc/reachcalendar.ics"
UID = "user-123"
WS = "workspace-987"


def _identity(ics: str | None) -> dict:
    s = get_settings()
    return {
        "uid": UID,
        "ck": crypto.encrypt_key(s.token_key, CLOCKIFY_KEY),
        "ws": WS,
        "ics": crypto.encrypt_key(s.token_key, ics) if ics else None,
    }


async def _provider_with_client():
    p = auth.StatelessClockifyOAuth()
    client = OAuthClientInformationFull(
        client_id="cowork",
        redirect_uris=[AnyUrl("https://claude.ai/cb")],
        token_endpoint_auth_method="none",
    )
    await p.register_client(client)
    return p, client


_TXN = {
    "cid": "cowork",
    "cc": "abc",
    "ru": "https://claude.ai/cb",
    "st": "xyz",
    "sc": ["clockify"],
}


@pytest.mark.asyncio
@pytest.mark.parametrize("ics", [ICS_URL, None])
async def test_identity_survives_full_chain_and_refresh(ics):
    p, client = await _provider_with_client()
    identity = _identity(ics)

    code_str = auth.mint_authorization_code(identity, _TXN)
    code = await p.load_authorization_code(client, code_str)
    tok = await p.exchange_authorization_code(client, code)

    access = await p.verify_token(tok.access_token)
    claims = access.claims
    # claims É a identity: as 4 chaves estão presentes
    assert set(claims) >= {"uid", "ck", "ws", "ics"}
    assert claims["uid"] == UID
    assert claims["ws"] == WS
    assert crypto.decrypt_key(get_settings().token_key, claims["ck"]) == CLOCKIFY_KEY
    if ics:
        assert crypto.decrypt_key(get_settings().token_key, claims["ics"]) == ICS_URL
    else:
        assert claims["ics"] is None

    # chave nunca em texto claro no token
    assert CLOCKIFY_KEY not in tok.access_token
    assert CLOCKIFY_KEY not in tok.refresh_token

    # CRÍTICO: refresh re-emite e ws/ics SOBREVIVEM (causa raiz do bug antigo)
    rt = await p.load_refresh_token(client, tok.refresh_token)
    tok2 = await p.exchange_refresh_token(client, rt, scopes=["clockify"])
    access2 = await p.verify_token(tok2.access_token)
    claims2 = access2.claims
    assert claims2["ws"] == WS
    assert claims2["uid"] == UID
    assert crypto.decrypt_key(get_settings().token_key, claims2["ck"]) == CLOCKIFY_KEY
    if ics:
        assert crypto.decrypt_key(get_settings().token_key, claims2["ics"]) == ICS_URL
    else:
        assert claims2["ics"] is None


@pytest.mark.asyncio
async def test_subject_is_the_whole_identity_json():
    """O subject do code/refresh é o identity inteiro serializado (não campos avulsos)."""
    p, client = await _provider_with_client()
    identity = _identity(ICS_URL)

    code_str = auth.mint_authorization_code(identity, _TXN)
    code = await p.load_authorization_code(client, code_str)
    assert json.loads(code.subject) == identity

    tok = await p.exchange_authorization_code(client, code)
    rt = await p.load_refresh_token(client, tok.refresh_token)
    assert json.loads(rt.subject) == identity


def test_decode_identity_builds_user_context():
    """A função de decodificação da identity -> UserContext (decifra ck/ics)."""
    identity = _identity(ICS_URL)
    ctx = context.decode_identity(identity)
    assert ctx.user_id == UID
    assert ctx.workspace_id == WS
    assert ctx.api_key == CLOCKIFY_KEY
    assert ctx.ics_url == ICS_URL

    ctx_no_ics = context.decode_identity(_identity(None))
    assert ctx_no_ics.ics_url is None
    assert ctx_no_ics.api_key == CLOCKIFY_KEY


def test_request_context_reads_access_token(monkeypatch):
    """request_context() lê get_access_token().claims e decifra a identity."""

    class _Tok:
        claims = None

    tok = _Tok()
    tok.claims = _identity(ICS_URL)
    monkeypatch.setattr(context, "get_access_token", lambda: tok)

    ctx = context.request_context()
    assert ctx.user_id == UID
    assert ctx.workspace_id == WS
    assert ctx.api_key == CLOCKIFY_KEY
    assert ctx.ics_url == ICS_URL
