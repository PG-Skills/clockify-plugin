"""FastMCP server: tool `whoami` (lê a chave via get_access_token().claims) +
a página /connect (coleta a chave do Clockify e fecha o fluxo OAuth)."""

import html
import urllib.parse

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_access_token

from . import auth, crypto
from .clockify import get_user
from .settings import get_settings

mcp = FastMCP(name="clockify-mcp", auth=auth.StatelessClockifyOAuth())


@mcp.tool
async def whoami() -> str:
    """Confirma a conexão: devolve o nome da conta do Clockify."""
    token = get_access_token()
    api_key = crypto.decrypt_key(get_settings().token_key, token.claims["ck"])
    user = await get_user(api_key)
    return f"Conectado como {user['name']} ({user['email']})."


_FORM = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Conectar o Clockify · PG</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#0a1a3f;color:#fff;display:grid;
   place-items:center;min-height:100vh;margin:0}}
 .card{{background:#fff;color:#0a1a3f;max-width:420px;padding:32px;border-radius:16px;
   box-shadow:0 10px 40px rgba(0,0,0,.3)}}
 h1{{font-size:20px;margin:0 0 4px}} p{{color:#475569;font-size:14px;line-height:1.5}}
 input{{width:100%;padding:12px;border:1px solid #cbd5e1;border-radius:8px;font-size:15px;
   box-sizing:border-box;margin:8px 0 4px}}
 button{{width:100%;padding:12px;border:0;border-radius:8px;background:#1e3a8a;color:#fff;
   font-size:15px;font-weight:600;cursor:pointer;margin-top:12px}}
 .err{{color:#dc2626;font-size:13px}} small{{color:#64748b}}
</style></head><body><div class="card">
 <h1>Conectar o Clockify</h1>
 <p>Cole sua chave do Clockify. Onde pegar: Clockify → canto superior direito (seu perfil)
    → <b>Preferences</b> → aba <b>Advanced</b> → <b>Generate</b>.</p>
 {err}
 <form method="post" action="/connect">
   <input type="hidden" name="txn" value="{txn}">
   <input name="api_key" placeholder="Sua chave do Clockify" autofocus required>
   <button type="submit">Conectar</button>
 </form>
 <small>Sua chave nunca é guardada no servidor — fica cifrada só na sua sessão.</small>
</div></body></html>"""


@mcp.custom_route("/connect", methods=["GET"])
async def connect_form(request: Request) -> HTMLResponse:
    txn = request.query_params.get("txn", "")
    return HTMLResponse(_FORM.format(txn=html.escape(txn, quote=True), err=""))


@mcp.custom_route("/connect", methods=["POST"])
async def connect_submit(request: Request):
    form = await request.form()
    txn_raw = str(form.get("txn", ""))
    api_key = str(form.get("api_key", "")).strip()
    txn = auth.read_txn(txn_raw)
    if not txn:
        return HTMLResponse(
            _FORM.format(
                txn=html.escape(txn_raw, quote=True),
                err='<p class="err">Sessão expirada. Recomece.</p>',
            ),
            status_code=400,
        )
    try:
        user = await get_user(api_key)
    except Exception:
        return HTMLResponse(
            _FORM.format(
                txn=html.escape(txn_raw, quote=True),
                err='<p class="err">Chave inválida. Confira e tente de novo.</p>',
            ),
            status_code=400,
        )
    code = auth.mint_authorization_code(user["id"], api_key, txn)
    q = urllib.parse.urlencode({"code": code, "state": txn["st"]})
    return RedirectResponse(f"{txn['ru']}?{q}", status_code=302)
