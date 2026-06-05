"""Tools MCP idioma-neutras.

INVARIANTE: cada tool devolve **dados** (dict/list, datas ISO, ids, números) — NUNCA
frases prontas pro usuário. Quem verbaliza na língua do usuário é a skill conversacional.

Cada tool lê `request_context()` para `api_key`/`workspace_id`/`user_id`/`ics_url` e
delega o IO confiável aos módulos `clockify`/`ics`/`resolve`/`prefs`. As funções de IO
são importadas com nomes locais (aliases) para serem facilmente mockáveis nos testes.
"""

from datetime import date as _date
from zoneinfo import ZoneInfo

from .clockify import entries as cl_entries
from .clockify import get_user
from .context import request_context
from .ics import events_for_day, fetch_ics
from .prefs import get_prefs as prefs_get
from .prefs import learn as prefs_learn
from .prefs import set_default as prefs_set_default
from .pure import business_days as pure_business_days
from .pure import day_window_utc, range_window_utc
from .resolve import add_entries as add_entries_io
from .resolve import resolve_activity as resolve_activity_io

# Mesmo fuso default usado em ics.py/resolve.py — entradas locais são America/Sao_Paulo.
_TZ = ZoneInfo("America/Sao_Paulo")


def _workspace(ctx) -> str:
    """Narrow do workspace_id (str | None -> str). Uma conexão válida sempre tem
    workspace (vem do /connect via get_user); ausência é estado inválido."""
    if ctx.workspace_id is None:
        raise RuntimeError("sem workspace no contexto atual")
    return ctx.workspace_id


def register(mcp) -> None:
    """Registra todas as tools idioma-neutras no servidor FastMCP `mcp`."""

    @mcp.tool
    async def whoami() -> dict:
        """Identidade da conta conectada: ``{name, email}`` (dados, sem frase)."""
        ctx = request_context()
        user = await get_user(ctx.api_key)
        return {"name": user["name"], "email": user["email"]}

    @mcp.tool
    async def agenda(date: str) -> dict:
        """Eventos do Outlook (ICS) num dia ``YYYY-MM-DD``.

        Sem ICS configurado: ``{"ics": false, "eventos": []}``. Com ICS: cada evento é
        ``{title, start, end}`` com datas em ISO (string), ordenado por início.
        """
        ctx = request_context()
        if ctx.ics_url is None:
            return {"ics": False, "eventos": []}
        ics_text = await fetch_ics(ctx.ics_url)
        eventos = events_for_day(ics_text, _date.fromisoformat(date), _TZ)
        return {
            "ics": True,
            "eventos": [
                {
                    "title": ev["title"],
                    "start": ev["start"].isoformat(),
                    "end": ev["end"].isoformat(),
                }
                for ev in eventos
            ],
        }

    @mcp.tool
    async def entries(start: str, end: str | None = None) -> list[dict]:
        """Time-entries crus do usuário na janela local (um dia ou intervalo inclusivo).

        ``start``/``end`` em ``YYYY-MM-DD``; ``end`` omitido => só o dia ``start``.
        Devolve a lista crua do Clockify (taskId, timeInterval, etc.).
        """
        ctx = request_context()
        start_d = _date.fromisoformat(start)
        if end is None:
            win_start, win_end = day_window_utc(start_d, _TZ)
        else:
            win_start, win_end = range_window_utc(
                start_d, _date.fromisoformat(end), _TZ
            )
        return await cl_entries(
            ctx.api_key, _workspace(ctx), ctx.user_id, win_start, win_end
        )

    @mcp.tool
    async def business_days(start: str, end: str) -> list[str]:
        """Dias úteis (seg–sex) no intervalo ``[start, end]`` inclusive, como ISO strings."""
        dias = pure_business_days(_date.fromisoformat(start), _date.fromisoformat(end))
        return [d.isoformat() for d in dias]

    @mcp.tool
    async def resolve_activity(name: str, project: str | None = None) -> dict:
        """Resolve (projeto -> tarefa) por nome. Repassa o dict estruturado do resolve
        (status OK/AMBIGUO/NAO_ENCONTRADO + candidatos)."""
        ctx = request_context()
        return await resolve_activity_io(
            ctx.api_key, _workspace(ctx), name=name, project=project
        )

    @mcp.tool
    async def add_entries(items: list[dict]) -> dict:
        """Grava vários time-entries (resolve + anti-duplicata). Cada item:
        ``{description, date "YYYY-MM-DD", start "HH:MM", end "HH:MM", task,
        project?, tag?, billable?}``. Repassa o dict de resultado do resolve."""
        ctx = request_context()
        return await add_entries_io(ctx.api_key, _workspace(ctx), ctx.user_id, items)

    @mcp.tool
    async def get_prefs() -> dict:
        """Preferências do usuário: ``{default, learned}`` (atividade padrão + aprendidas)."""
        ctx = request_context()
        return prefs_get(ctx.user_id)

    @mcp.tool
    async def learn_activity(
        match: str,
        project: str,
        task: str | None = None,
        tag: str | None = None,
        billable: bool | None = None,
    ) -> dict:
        """Aprende uma atividade (palavra-chave -> destino). Ack mínimo ``{"ok": true}``."""
        ctx = request_context()
        prefs_learn(
            ctx.user_id,
            match,
            project=project,
            task=task,
            tag=tag,
            billable=billable,
        )
        return {"ok": True}

    @mcp.tool
    async def set_default(
        project: str | None = None,
        task: str | None = None,
        tag: str | None = None,
        billable: bool | None = None,
        daily_target: float | None = None,
    ) -> dict:
        """Define a atividade padrão do usuário. Ack mínimo ``{"ok": true}``."""
        ctx = request_context()
        prefs_set_default(
            ctx.user_id,
            project=project,
            task=task,
            tag=tag,
            billable=billable,
            daily_target=daily_target,
        )
        return {"ok": True}
