"""Resolução direcionada (nome -> IDs) e gravação em lote com anti-duplicata.
Porta SÍNCRONA de server/resolve.py — mesma lógica, sem async. `cl` aponta para o
módulo clockify (substituível nos testes)."""

from datetime import (
    date,
    datetime,
    timezone,
)  # timezone usado no anti-duplicata por instante
from zoneinfo import ZoneInfo

import clockify as cl
from pure import range_window_utc, to_utc_iso

_TZ = ZoneInfo("America/Sao_Paulo")


def _candidatos(items: list[dict]) -> list[dict]:
    return [{"id": it["id"], "name": it.get("name", "")} for it in items]


def resolve_activity(api_key, workspace_id, *, name, project=None, tag=None) -> dict:
    if project is None:
        return {"status": "AMBIGUO", "motivo": "projeto necessário", "candidatos": []}

    projs = cl.search_projects(api_key, workspace_id, project)
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

    tasks = cl.tasks_in_project(api_key, workspace_id, project_id, name)
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
        tags = cl.search_tags(api_key, workspace_id, tag)
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


def _local_dt(d: str, hhmm: str) -> datetime:
    """`'2026-01-28'` + `'9:00'`/`'09:00'` -> datetime aware no fuso local.
    Constrói explicitamente (não usa fromisoformat) p/ aceitar hora sem zero à esquerda
    e funcionar em Python 3.10 (que é estrito com HH:MM sem segundos)."""
    y, mo, da = (int(x) for x in d.split("-"))
    parts = hhmm.split(":")
    hh = int(parts[0])
    mm = int(parts[1]) if len(parts) > 1 else 0
    return datetime(y, mo, da, hh, mm, tzinfo=_TZ)


def _entry_start_instant(entry: dict) -> datetime | None:
    """Instante de início (UTC aware) de um entry cru do Clockify, p/ casar duplicata exata."""
    start = (entry.get("timeInterval") or {}).get("start")
    if not start:
        return None
    return datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(timezone.utc)


def add_entries(api_key, workspace_id, user_id, items: list[dict]) -> dict:
    total = len(items)
    if total == 0:
        return {
            "gravados": 0,
            "total": 0,
            "pulados_duplicata": 0,
            "falhou_em": None,
            "motivo": None,
        }

    datas = [date.fromisoformat(it["date"]) for it in items]
    win_start, win_end = range_window_utc(min(datas), max(datas), _TZ)
    existentes = cl.entries(api_key, workspace_id, user_id, win_start, win_end)
    # Duplicata EXATA = mesma tarefa E mesmo início (re-run). Blocos diferentes da mesma
    # tarefa no mesmo dia (09-10, 11-12, 13-18) têm starts distintos -> entram normalmente.
    ja_existe: set[tuple[str, datetime]] = set()
    for e in existentes:
        inst = _entry_start_instant(e)
        tid = e.get("taskId")
        if inst and tid:
            ja_existe.add((tid, inst))

    gravados = 0
    pulados = 0
    for idx, item in enumerate(items):
        res = resolve_activity(
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

        start_local = _local_dt(item["date"], item["start"])
        chave = (res["task_id"], start_local.astimezone(timezone.utc))
        if chave in ja_existe:
            pulados += 1
            continue

        payload = {
            "start": to_utc_iso(start_local),
            "end": to_utc_iso(_local_dt(item["date"], item["end"])),
            "description": item.get("description", ""),
            "projectId": res["project_id"],
            "taskId": res["task_id"],
            "tagIds": res["tag_ids"],
            "billable": item.get("billable", False),
        }
        cl.create_entry(api_key, workspace_id, payload)
        gravados += 1
        ja_existe.add(chave)

    return {
        "gravados": gravados,
        "total": total,
        "pulados_duplicata": pulados,
        "falhou_em": None,
        "motivo": None,
    }
