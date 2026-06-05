"""Resolução direcionada (nome -> IDs) e gravação em lote com anti-duplicata.

Reusa o CONCEITO do v1.0 (`entries.build_payload`/`_resolve_task`) mas o IO é a busca
direcionada do `clockify.py` (o endpoint de tasks do Clockify EXIGE projectId — não há
busca global de tarefa). Por isso resolver tarefa sem projeto é impossível: devolvemos
AMBIGUO ("projeto necessário") e a skill conversacional fornece o `project` (atividade
aprendida / padrão) antes de chamar.

Retornos estruturados são idioma-neutro: só dados (status/motivo/candidatos), NUNCA
frase pronta pro usuário — quem fala com o usuário é a skill conversacional.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from . import clockify as cl
from .pure import to_utc_iso

# Mesmo default de fuso usado em ics.py — horários dos items chegam em hora local.
_TZ = ZoneInfo("America/Sao_Paulo")


def _candidatos(items: list[dict]) -> list[dict]:
    """Reduz os matches do Clockify a {id, name} — evita vazar payload cru pra resposta."""
    return [{"id": it["id"], "name": it.get("name", "")} for it in items]


async def resolve_activity(
    api_key: str,
    workspace_id: str,
    *,
    name: str,
    project: str | None = None,
    tag: str | None = None,
) -> dict:
    """Resolve (projeto -> tarefa [-> tag]) por nome via busca direcionada.

    - `project` None: impossível resolver tarefa (endpoint exige projectId). Retorna
      AMBIGUO "projeto necessário" — guard do W-1 (a skill fornece o projeto).
    - 0 ou >=2 matches de projeto/tarefa/tag: AMBIGUO / NAO_ENCONTRADO com candidatos.
    - Sucesso: {"status": "OK", "project_id", "task_id", "tag_ids"}.
    """
    if project is None:
        return {
            "status": "AMBIGUO",
            "motivo": "projeto necessário",
            "candidatos": [],
        }

    projs = await cl.search_projects(api_key, workspace_id, project)
    if len(projs) == 0:
        return {
            "status": "NAO_ENCONTRADO",
            "motivo": "projeto não encontrado",
            "candidatos": [],
        }
    if len(projs) > 1:
        return {
            "status": "AMBIGUO",
            "motivo": "projeto ambíguo",
            "candidatos": _candidatos(projs),
        }
    project_id = projs[0]["id"]

    tasks = await cl.tasks_in_project(api_key, workspace_id, project_id, name)
    if len(tasks) == 0:
        return {
            "status": "NAO_ENCONTRADO",
            "motivo": "tarefa não encontrada",
            "candidatos": [],
        }
    if len(tasks) > 1:
        return {
            "status": "AMBIGUO",
            "motivo": "tarefa ambígua",
            "candidatos": _candidatos(tasks),
        }
    task_id = tasks[0]["id"]

    tag_ids: list[str] = []
    if tag:
        tags = await cl.search_tags(api_key, workspace_id, tag)
        if len(tags) == 0:
            return {
                "status": "NAO_ENCONTRADO",
                "motivo": "etiqueta não encontrada",
                "candidatos": [],
            }
        if len(tags) > 1:
            return {
                "status": "AMBIGUO",
                "motivo": "etiqueta ambígua",
                "candidatos": _candidatos(tags),
            }
        tag_ids = [tags[0]["id"]]

    return {
        "status": "OK",
        "project_id": project_id,
        "task_id": task_id,
        "tag_ids": tag_ids,
    }


def _local_dt(date: str, hhmm: str) -> datetime:
    """`'2026-01-28'` + `'09:00'` -> datetime aware no fuso local."""
    return datetime.fromisoformat(f"{date}T{hhmm}").replace(tzinfo=_TZ)


def _entry_local_date(entry: dict) -> str | None:
    """Data local (YYYY-MM-DD) do início de um entry cru do Clockify (start em UTC)."""
    start = (entry.get("timeInterval") or {}).get("start")
    if not start:
        return None
    # Clockify devolve ...Z; fromisoformat aceita Z a partir do 3.11.
    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return dt.astimezone(_TZ).date().isoformat()


async def add_entries(
    api_key: str,
    workspace_id: str,
    user_id: str,
    items: list[dict],
) -> dict:
    """Resolve e grava cada item, na ordem. Para no 1º erro (semântica do v1.0).

    Cada item: {description, date, start, end, task, project?, tag?, billable?} em hora
    local. Anti-duplicata: lê os entries existentes na janela dos items UMA vez e pula
    qualquer item cujo (data local, taskId) já exista — não chama create_entry pra ele.

    Retorna {"gravados", "total", "pulados_duplicata", "falhou_em", "motivo"}.
    """
    total = len(items)
    if total == 0:
        return {
            "gravados": 0,
            "total": 0,
            "pulados_duplicata": 0,
            "falhou_em": None,
            "motivo": None,
        }

    # Janela UTC que cobre todos os items -> uma única leitura de entries existentes.
    starts = [_local_dt(it["date"], it["start"]) for it in items]
    ends = [_local_dt(it["date"], it["end"]) for it in items]
    win_start = to_utc_iso(min(starts))
    win_end = to_utc_iso(max(ends))
    existentes = await cl.entries(api_key, workspace_id, user_id, win_start, win_end)
    ja_existe: set[tuple[str, str]] = set()
    for e in existentes:
        d = _entry_local_date(e)
        tid = e.get("taskId")
        if d and tid:
            ja_existe.add((d, tid))

    gravados = 0
    pulados = 0
    for idx, item in enumerate(items):
        res = await resolve_activity(
            api_key,
            workspace_id,
            name=item["task"],
            project=item.get("project"),
            tag=item.get("tag"),
        )
        if res["status"] != "OK":
            return {
                "gravados": gravados,
                "total": total,
                "pulados_duplicata": pulados,
                "falhou_em": idx,
                "motivo": res["motivo"],
            }

        chave = (item["date"], res["task_id"])
        if chave in ja_existe:
            pulados += 1
            continue

        payload = {
            "start": to_utc_iso(_local_dt(item["date"], item["start"])),
            "end": to_utc_iso(_local_dt(item["date"], item["end"])),
            "description": item.get("description", ""),
            "projectId": res["project_id"],
            "taskId": res["task_id"],
            "tagIds": res["tag_ids"],
            "billable": item.get("billable", False),
        }
        await cl.create_entry(api_key, workspace_id, payload)
        gravados += 1
        # Marca para não duplicar entre items idênticos no mesmo lote.
        ja_existe.add(chave)

    return {
        "gravados": gravados,
        "total": total,
        "pulados_duplicata": pulados,
        "falhou_em": None,
        "motivo": None,
    }
