"""Integração HTTP: rotas OAuth expostas, 401 sem token, e a página /connect."""

import httpx
import pytest
import respx
from httpx import ASGITransport

from clockify_mcp.app import mcp


async def _client(app):
    transport = ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    )


@pytest.mark.asyncio
async def test_oauth_metadata_and_401():
    app = mcp.http_app()
    async with app.router.lifespan_context(app):
        async with await _client(app) as c:
            r = await c.get("/.well-known/oauth-authorization-server")
            assert r.status_code == 200
            assert "authorization_endpoint" in r.json()
            r = await c.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "t", "version": "1"},
                    },
                },
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                },
            )
            assert r.status_code == 401
            assert "resource_metadata" in (r.headers.get("www-authenticate") or "")


@pytest.mark.asyncio
async def test_connect_form_and_submit():
    app = mcp.http_app()
    async with app.router.lifespan_context(app):
        async with await _client(app) as c:
            # GET /connect mostra o form
            r = await c.get("/connect", params={"txn": "x"})
            assert r.status_code == 200 and "Clockify" in r.text
            # POST /connect com chave válida -> 302 com code
            from clockify_mcp import auth
            from mcp.server.auth.provider import AuthorizationParams
            from pydantic import AnyUrl

            txn = auth.mint_txn(
                AuthorizationParams(
                    state="xyz",
                    scopes=["clockify"],
                    code_challenge="abc",
                    redirect_uri=AnyUrl("https://claude.ai/cb"),
                    redirect_uri_provided_explicitly=True,
                    resource="http://localhost:8080/mcp",
                ),
                "cowork",
            )
            with respx.mock:
                respx.get("https://api.clockify.me/api/v1/user").mock(
                    return_value=httpx.Response(
                        200, json={"id": "u1", "name": "Ana", "email": "ana@pg.com"}
                    )
                )
                r = await c.post("/connect", data={"txn": txn, "api_key": "KEY"})
            assert r.status_code == 302
            assert (
                "code=" in r.headers["location"]
                and "state=xyz" in r.headers["location"]
            )


@pytest.mark.asyncio
async def test_connect_form_i18n_and_ics_field():
    """A página /connect é multilíngue (Accept-Language) e expõe o campo ICS opcional."""
    app = mcp.http_app()
    async with app.router.lifespan_context(app):
        async with await _client(app) as c:
            # Inglês via Accept-Language -> textos em inglês + campo ics_url.
            r_en = await c.get(
                "/connect",
                params={"txn": "x"},
                headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            assert r_en.status_code == 200
            assert "Connect Clockify" in r_en.text
            assert 'name="ics_url"' in r_en.text
            assert "optional" in r_en.text.lower()

            # Sem header -> default português.
            r_pt = await c.get("/connect", params={"txn": "x"})
            assert r_pt.status_code == 200
            assert "Conectar o Clockify" in r_pt.text
            assert "Conectar" not in r_en.text  # rótulo PT não vaza no EN
            assert 'name="ics_url"' in r_pt.text


@pytest.mark.asyncio
async def test_connect_form_escapes_txn_xss():
    """Regressão: txn refletido na página /connect deve ser HTML-escapado."""
    app = mcp.http_app()
    async with app.router.lifespan_context(app):
        async with await _client(app) as c:
            r = await c.get("/connect", params={"txn": '"><script>alert(1)</script>'})
            assert r.status_code == 200
            assert "<script>alert(1)</script>" not in r.text
            assert "&lt;script&gt;" in r.text
