import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clockify_horas.clockify_api import ClockifyClient
from clockify_horas.config import load_config
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
    """Lista lançamentos já existentes no dia — usado pelo /horas p/ anti-duplicata."""
    cfg = load_config()
    target = date.fromisoformat(args.date) if args.date else date.today()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    user_id = client.get_user_id()
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

    for p in payloads:
        resp = client.create_entry(p)
        print(f"Lançado: {p['description']} -> {resp.get('id')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clockify-horas")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_agenda = sub.add_parser("agenda", help="Lê a agenda do Outlook (ICS) de um dia")
    p_agenda.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_agenda.set_defaults(func=_cmd_agenda)

    p_meta = sub.add_parser("meta", help="Lista projetos/tarefas/tags do workspace")
    p_meta.set_defaults(func=_cmd_meta)

    p_entries = sub.add_parser("entries", help="Lista lançamentos existentes no dia")
    p_entries.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_entries.set_defaults(func=_cmd_entries)

    p_add = sub.add_parser("add", help="Cria lançamentos a partir de um JSON")
    p_add.add_argument("--file", required=True, help="Arquivo JSON com a lista de lançamentos")
    p_add.add_argument("--dry-run", action="store_true", help="Imprime payloads sem postar")
    p_add.set_defaults(func=_cmd_add)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
