"""Núcleo: cripto, cliente Clockify e o ciclo OAuth stateless (incl. refresh = C3)."""

import os

import httpx
import pytest
import respx

from clockify_mcp import auth, crypto
from clockify_mcp.clockify import get_user
from clockify_mcp.settings import get_settings

CLOCKIFY_KEY = "Yjk2-clockify-secret-NUNCA-EM-TEXTO"
UID = "user-123"


def test_crypto_roundtrip():
    master = os.urandom(32)
    blob = crypto.encrypt_key(master, "KEY")
    assert blob != "KEY"
    assert crypto.decrypt_key(master, blob) == "KEY"


@respx.mock
@pytest.mark.asyncio
async def test_get_user_ok_and_bad():
    respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(
            200, json={"id": "u1", "name": "Ana", "email": "ana@pg.com"}
        )
    )
    assert (await get_user("KEY"))["name"] == "Ana"
    respx.get("https://api.clockify.me/api/v1/user").mock(
        return_value=httpx.Response(401)
    )
    with pytest.raises(ValueError):
        await get_user("BAD")


@pytest.mark.asyncio
async def test_oauth_cycle_stateless_with_refresh():
    p = auth.StatelessClockifyOAuth()
    from mcp.shared.auth import OAuthClientInformationFull
    from pydantic import AnyUrl

    client = OAuthClientInformationFull(
        client_id="cowork",
        redirect_uris=[AnyUrl("https://claude.ai/cb")],
        token_endpoint_auth_method="none",
    )
    await p.register_client(client)

    # A página /connect validou a chave e emitiu o code (carregando ck).
    txn = {
        "cid": "cowork",
        "cc": "abc",
        "ru": "https://claude.ai/cb",
        "st": "xyz",
        "sc": ["clockify"],
    }
    code_str = auth.mint_authorization_code(UID, CLOCKIFY_KEY, txn)

    code = await p.load_authorization_code(client, code_str)
    tok = await p.exchange_authorization_code(client, code)
    access = await p.verify_token(tok.access_token)
    assert (
        crypto.decrypt_key(get_settings().token_key, access.claims["ck"])
        == CLOCKIFY_KEY
    )
    assert (
        CLOCKIFY_KEY not in tok.access_token and CLOCKIFY_KEY not in tok.refresh_token
    )

    # C3: refresh re-emite com a chave, sem recoletar.
    rt = await p.load_refresh_token(client, tok.refresh_token)
    tok2 = await p.exchange_refresh_token(client, rt, scopes=["clockify"])
    access2 = await p.verify_token(tok2.access_token)
    assert (
        crypto.decrypt_key(get_settings().token_key, access2.claims["ck"])
        == CLOCKIFY_KEY
    )

    assert await p.verify_token("not.a.jwt") is None
