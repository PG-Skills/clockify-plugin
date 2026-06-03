import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from clockify_horas.bizdays import business_days
from clockify_horas.clockify_api import ClockifyClient
from clockify_horas.config import (
    config_path,
    load_config,
    read_raw,
    write_raw,
)
from clockify_horas.entries import build_payload
from clockify_horas.ics import fetch_ics, parse_ics
from clockify_horas.models import TimeEntry

_TZ = ZoneInfo("America/Sao_Paulo")


def _parse_local(value: str) -> datetime:
    """ISO8601 -> datetime aware. Se vier sem offset, assume o fuso local."""
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_TZ)


def _cmd_agenda(args: argparse.Namespace) -> int:
    cfg = load_config()
    target = date.fromisoformat(args.date) if args.date else date.today()
    eventos = parse_ics(fetch_ics(cfg.ics_url), target_date=target, tz=_TZ)
    payload = [
        {"title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat()} for e in eventos
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_meta(args: argparse.Namespace) -> int:
    cfg = load_config()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    md = client.get_metadata()
    out = {
        "workspace_id": md.workspace_id,
        "user_id": md.user_id,
        "projects": md.projects,
        "tasks": {f"{pid} :: {name}": tid for (pid, name), tid in md.tasks.items()},
        "tags": md.tags,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _cmd_entries(args: argparse.Namespace) -> int:
    """Lista lançamentos existentes — um dia (--date) ou intervalo (--start/--end).

    --date: imprime lista do dia. Intervalo: imprime objeto agrupado por data local.
    """
    if not args.date and not (args.start and args.end):
        print("erro: informe --date OU --start e --end", file=sys.stderr)
        return 2

    cfg = load_config()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    user_id = client.get_user_id()

    if args.start and args.end:
        existentes = client.get_entries_for_range(
            user_id, date.fromisoformat(args.start), date.fromisoformat(args.end), _TZ
        )
        por_data: dict[str, list[dict[str, Any]]] = {}
        for e in existentes:
            ini = e.get("timeInterval", {}).get("start")
            if not ini:
                continue
            local_date = datetime.fromisoformat(ini.replace("Z", "+00:00")).astimezone(_TZ).date()
            por_data.setdefault(local_date.isoformat(), []).append(
                {"id": e.get("id"), "description": e.get("description"), "start": ini}
            )
        print(json.dumps(por_data, ensure_ascii=False, indent=2))
        return 0

    target = date.fromisoformat(args.date) if args.date else date.today()
    existentes = client.get_entries_for_date(user_id, target, _TZ)
    resumo = [
        {
            "id": e.get("id"),
            "description": e.get("description"),
            "start": e.get("timeInterval", {}).get("start"),
            "end": e.get("timeInterval", {}).get("end"),
        }
        for e in existentes
    ]
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


def _cmd_business_days(args: argparse.Namespace) -> int:
    dias = business_days(date.fromisoformat(args.start), date.fromisoformat(args.end))
    print(json.dumps([d.isoformat() for d in dias], ensure_ascii=False, indent=2))
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    cfg = load_config()
    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    entries = [
        TimeEntry(
            description=item["description"],
            start=_parse_local(item["start"]),
            end=_parse_local(item["end"]),
            task_name=item["task_name"],
            tag_names=item["tag_names"],
            billable=bool(item["billable"]),
        )
        for item in raw
    ]
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    md = client.get_metadata()
    payloads = [build_payload(e, md) for e in entries]

    if args.dry_run:
        print(json.dumps(payloads, ensure_ascii=False, indent=2))
        return 0

    gravados: list[Any] = []
    for i, p in enumerate(payloads, start=1):
        try:
            resp = client.create_entry(p)
        except httpx.HTTPError as e:
            desc = p["description"]
            print(
                f"FALHA no item {i}/{len(payloads)} ({desc} @ {p['start']}): {e}", file=sys.stderr
            )
            print(
                f"Gravados com sucesso antes da falha: {len(gravados)}/{len(payloads)}. "
                f"Reexecute apenas os itens restantes para evitar duplicata.",
                file=sys.stderr,
            )
            return 1
        gravados.append(resp.get("id"))
        print(f"Lançado: {p['description']} -> {resp.get('id')}")
    return 0


def _cmd_config_set(args: argparse.Namespace) -> int:
    data = read_raw()
    ck = data.setdefault("clockify", {})
    ol = data.setdefault("outlook", {})
    df = data.setdefault("defaults", {})
    data.setdefault("overrides", [])
    if args.api_key is not None:
        ck["api_key"] = args.api_key
    if args.workspace_id is not None:
        ck["workspace_id"] = args.workspace_id
    if args.ics_url is not None:
        ol["ics_url"] = args.ics_url
    if args.task is not None:
        df["task_name"] = args.task
    if args.tag is not None:
        df["tag_name"] = args.tag
    if args.billable is not None:
        df["billable"] = args.billable
    if args.daily_target is not None:
        df["daily_target_hours"] = float(args.daily_target)
    p = write_raw(data)
    print(f"Config atualizada: {p}")
    return 0


def _cmd_config_path(args: argparse.Namespace) -> int:
    print(str(config_path()))
    return 0


def _cmd_config_show(args: argparse.Namespace) -> int:
    data = read_raw()
    if not data:
        print("Sem config. Rode /clockify-setup.", file=sys.stderr)
        return 1
    red = json.loads(json.dumps(data))
    if red.get("clockify", {}).get("api_key"):
        red["clockify"]["api_key"] = "***"
    print(json.dumps(red, ensure_ascii=False, indent=2))
    return 0


def _cmd_config_add_override(args: argparse.Namespace) -> int:
    data = read_raw()
    ov = data.setdefault("overrides", [])
    ov.append(
        {
            "match": args.match,
            "task_name": args.task,
            "tag_name": args.tag,
            "billable": bool(args.billable) if args.billable is not None else False,
        }
    )
    p = write_raw(data)
    print(f"Override adicionado ({args.match}): {p}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clockify-horas")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_agenda = sub.add_parser("agenda", help="Lê a agenda do Outlook (ICS) de um dia")
    p_agenda.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_agenda.set_defaults(func=_cmd_agenda)

    p_meta = sub.add_parser("meta", help="Lista projetos/tarefas/tags do workspace")
    p_meta.set_defaults(func=_cmd_meta)

    p_entries = sub.add_parser("entries", help="Lista lançamentos (--date OU --start/--end)")
    p_entries.add_argument("--date", help="AAAA-MM-DD (um dia)")
    p_entries.add_argument("--start", help="AAAA-MM-DD (início do intervalo)")
    p_entries.add_argument("--end", help="AAAA-MM-DD (fim do intervalo)")
    p_entries.set_defaults(func=_cmd_entries)

    p_bd = sub.add_parser("business-days", help="Lista dias úteis (seg–sex) de um intervalo")
    p_bd.add_argument("--start", required=True, help="AAAA-MM-DD")
    p_bd.add_argument("--end", required=True, help="AAAA-MM-DD")
    p_bd.set_defaults(func=_cmd_business_days)

    p_add = sub.add_parser("add", help="Cria lançamentos a partir de um JSON")
    p_add.add_argument("--file", required=True, help="Arquivo JSON com a lista de lançamentos")
    p_add.add_argument("--dry-run", action="store_true", help="Imprime payloads sem postar")
    p_add.set_defaults(func=_cmd_add)

    p_config = sub.add_parser("config", help="Gerencia a config por-usuário")
    config_sub = p_config.add_subparsers(dest="config_cmd", required=True)

    p_set = config_sub.add_parser("set", help="Define campos da config")
    p_set.add_argument("--api-key")
    p_set.add_argument("--workspace-id")
    p_set.add_argument("--ics-url")
    p_set.add_argument("--task")
    p_set.add_argument("--tag")
    p_set.add_argument("--daily-target")
    bill = p_set.add_mutually_exclusive_group()
    bill.add_argument("--billable", dest="billable", action="store_const", const=True, default=None)
    bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_set.set_defaults(func=_cmd_config_set)

    p_path = config_sub.add_parser("path", help="Imprime o caminho do arquivo de config")
    p_path.set_defaults(func=_cmd_config_path)

    p_show = config_sub.add_parser("show", help="Imprime a config (api_key redigida)")
    p_show.set_defaults(func=_cmd_config_show)

    p_ovr = config_sub.add_parser("add-override", help="Adiciona regra de override por cliente")
    p_ovr.add_argument("--match", required=True, help="Palavra-chave do cliente/projeto")
    p_ovr.add_argument("--task", required=True)
    p_ovr.add_argument("--tag", required=True)
    ovr_bill = p_ovr.add_mutually_exclusive_group()
    ovr_bill.add_argument(
        "--billable", dest="billable", action="store_const", const=True, default=None
    )
    ovr_bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_ovr.set_defaults(func=_cmd_config_add_override)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
