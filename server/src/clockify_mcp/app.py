"""FastMCP server: registra as tools idioma-neutras (`tools.register`) + a página
/connect (coleta a chave do Clockify e fecha o fluxo OAuth)."""

import html
import urllib.parse

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from fastmcp import FastMCP

from . import auth, crypto, ics, tools
from .clockify import get_user
from .settings import get_settings

mcp = FastMCP(name="clockify-mcp", auth=auth.StatelessClockifyOAuth())
tools.register(mcp)


_FORM = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · PG</title>
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
 label{{display:block;font-size:13px;font-weight:600;color:#0a1a3f;margin-top:12px}}
</style></head><body><div class="card">
 <h1>{title}</h1>
 <p>{instr}</p>
 {err}
 <form method="post" action="/connect">
   <input type="hidden" name="txn" value="{txn}">
   <label>{key_label}</label>
   <input name="api_key" placeholder="{key_ph}" autofocus required>
   <label>{ics_label}</label>
   <input name="ics_url" placeholder="{ics_ph}">
   <button type="submit">{button}</button>
 </form>
 <small>{footer}</small>
</div></body></html>"""


# Textos por idioma (PT default). Mantém o encanamento i18n simples e contido.
_STRINGS = {
    "pt": {
        "lang": "pt-br",
        "title": "Conectar o Clockify",
        "instr": (
            "Cole sua chave do Clockify. Onde pegar: Clockify &rarr; canto superior direito "
            "(seu perfil) &rarr; <b>Preferences</b> &rarr; aba <b>Advanced</b> &rarr; "
            "<b>Generate</b>."
        ),
        "key_label": "Chave do Clockify",
        "key_ph": "Sua chave do Clockify",
        "ics_label": "Link da agenda do Outlook (opcional)",
        "ics_ph": "Opcional &mdash; pode pular",
        "button": "Conectar",
        "footer": "Sua chave nunca é guardada no servidor — fica cifrada só na sua sessão.",
        "expired": "Sessão expirada. Recomece.",
        "invalid": "Chave inválida. Confira e tente de novo.",
        "bad_ics": "Link da agenda inválido. Use um link https público — ou deixe em branco.",
    },
    "en": {
        "lang": "en",
        "title": "Connect Clockify",
        "instr": (
            "Paste your Clockify key. Where to find it: Clockify &rarr; top-right corner "
            "(your profile) &rarr; <b>Preferences</b> &rarr; <b>Advanced</b> tab &rarr; "
            "<b>Generate</b>."
        ),
        "key_label": "Clockify key",
        "key_ph": "Your Clockify key",
        "ics_label": "Outlook calendar link (optional)",
        "ics_ph": "Optional &mdash; you can skip it",
        "button": "Connect",
        "footer": "Your key is never stored on the server — it stays encrypted in your session only.",
        "expired": "Session expired. Please start over.",
        "invalid": "Invalid key. Check it and try again.",
        "bad_ics": "Invalid calendar link. Use a public https link — or leave it blank.",
    },
    "es": {
        "lang": "es",
        "title": "Conectar Clockify",
        "instr": (
            "Pega tu clave de Clockify. Dónde encontrarla: Clockify &rarr; esquina superior "
            "derecha (tu perfil) &rarr; <b>Preferences</b> &rarr; pestaña <b>Advanced</b> "
            "&rarr; <b>Generate</b>."
        ),
        "key_label": "Clave de Clockify",
        "key_ph": "Tu clave de Clockify",
        "ics_label": "Enlace del calendario de Outlook (opcional)",
        "ics_ph": "Opcional &mdash; puedes omitirlo",
        "button": "Conectar",
        "footer": "Tu clave nunca se guarda en el servidor — queda cifrada solo en tu sesión.",
        "expired": "Sesión expirada. Empieza de nuevo.",
        "invalid": "Clave inválida. Verifícala e inténtalo de nuevo.",
        "bad_ics": "Enlace del calendario inválido. Usa un enlace https público — o déjalo vacío.",
    },
}


def _pick_lang(accept_language: str) -> str:
    """Idioma a partir do header ``Accept-Language``. PT é default; EN/ES quando o
    primeiro idioma com peso reconhecível bate. Simples e tolerante a header ausente."""
    if not accept_language:
        return "pt"
    # Primeiro item da lista (maior prioridade), só o código de idioma base.
    first = accept_language.split(",")[0].strip().lower()
    code = first.split(";")[0].split("-")[0]
    return code if code in _STRINGS else "pt"


def _render_form(txn_raw: str, lang: str, err: str = "") -> str:
    s = _STRINGS[lang]
    return _FORM.format(
        lang=s["lang"],
        title=s["title"],
        instr=s["instr"],
        key_label=s["key_label"],
        key_ph=s["key_ph"],
        ics_label=s["ics_label"],
        ics_ph=s["ics_ph"],
        button=s["button"],
        footer=s["footer"],
        txn=html.escape(txn_raw, quote=True),
        err=err,
    )


@mcp.custom_route("/connect", methods=["GET"])
async def connect_form(request: Request) -> HTMLResponse:
    txn = request.query_params.get("txn", "")
    lang = _pick_lang(request.headers.get("accept-language", ""))
    return HTMLResponse(_render_form(txn, lang))


@mcp.custom_route("/connect", methods=["POST"])
async def connect_submit(request: Request):
    form = await request.form()
    txn_raw = str(form.get("txn", ""))
    api_key = str(form.get("api_key", "")).strip()
    lang = _pick_lang(request.headers.get("accept-language", ""))
    txn = auth.read_txn(txn_raw)
    if not txn:
        return HTMLResponse(
            _render_form(
                txn_raw,
                lang,
                err=f'<p class="err">{_STRINGS[lang]["expired"]}</p>',
            ),
            status_code=400,
        )
    try:
        user = await get_user(api_key)
    except Exception:
        return HTMLResponse(
            _render_form(
                txn_raw,
                lang,
                err=f'<p class="err">{_STRINGS[lang]["invalid"]}</p>',
            ),
            status_code=400,
        )
    settings = get_settings()
    # Campo ICS opcional do form; None quando a pessoa pula. Quando preenchido, valida
    # (anti-SSRF) ANTES de emitir o code — URL interna/privada não vira token.
    ics_url = str(form.get("ics_url", "")).strip() or None
    if ics_url is not None:
        try:
            ics._validate_ics_url(ics_url)
        except ValueError:
            return HTMLResponse(
                _render_form(
                    txn_raw,
                    lang,
                    err=f'<p class="err">{_STRINGS[lang]["bad_ics"]}</p>',
                ),
                status_code=400,
            )
    identity = {
        "uid": user["id"],
        "ck": crypto.encrypt_key(settings.token_key, api_key),
        "ws": user["workspace_id"],
        "ics": crypto.encrypt_key(settings.token_key, ics_url) if ics_url else None,
    }
    code = auth.mint_authorization_code(identity, txn)
    q = urllib.parse.urlencode({"code": code, "state": txn["st"]})
    return RedirectResponse(f"{txn['ru']}?{q}", status_code=302)
