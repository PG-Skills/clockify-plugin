import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from clockify_plugin import learned
from clockify_plugin.bizdays import business_days
from clockify_plugin.clockify_api import ClockifyClient
from clockify_plugin.config import (
    config_path,
    load_api_key,
    load_config,
    load_defaults,
    read_raw,
    write_raw,
)
from clockify_plugin.entries import build_payload
from clockify_plugin.ics import fetch_ics, parse_ics
from clockify_plugin.models import TimeEntry

_TZ = ZoneInfo("America/Sao_Paulo")


def _parse_local(value: str) -> datetime:
    """ISO8601 -> datetime aware. Se vier sem offset, assume o fuso local."""
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_TZ)


def _cmd_workspaces(args: argparse.Namespace) -> int:
    client = ClockifyClient(load_api_key(), "")
    ws = client.list_workspaces()
    print(
        json.dumps(
            [{"id": w["id"], "name": w.get("name")} for w in ws], ensure_ascii=False, indent=2
        )
    )
    return 0


def _cmd_agenda(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not cfg.ics_url:
        print(
            "erro: ICS não configurado. Rode /clockify-setup para o fluxo do Outlook.",
            file=sys.stderr,
        )
        return 2
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
    try:
        raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"erro: arquivo não encontrado: {args.file}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"erro: JSON inválido em {args.file}: {e}", file=sys.stderr)
        return 1
    try:
        entries = [
            TimeEntry(
                description=item["description"],
                start=_parse_local(item["start"]),
                end=_parse_local(item["end"]),
                task_name=item["task_name"],
                tag_names=item["tag_names"],
                billable=bool(item["billable"]),
                project_name=item.get("project_name"),
            )
            for item in raw
        ]
    except KeyError as e:
        print(f"erro: campo ausente no JSON do lançamento: {e}", file=sys.stderr)
        return 1
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    md = client.get_metadata()
    try:
        payloads = [build_payload(e, md) for e in entries]
    except KeyError as e:
        print(f"erro: {e}", file=sys.stderr)
        return 1

    if args.dry_run:
        print(json.dumps(payloads, ensure_ascii=False, indent=2))
        return 0

    gravados: list[Any] = []
    for i, (entry, p) in enumerate(zip(entries, payloads, strict=True), start=1):
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
        learned.record(
            match=entry.description,
            project_name=entry.project_name,
            task_name=entry.task_name,
            tag_names=entry.tag_names,
            billable=entry.billable,
        )
        print(f"Lançado: {p['description']} -> {resp.get('id')}")
    return 0


def _cmd_config_set(args: argparse.Namespace) -> int:
    data = read_raw()
    ck = data.setdefault("clockify", {})
    ol = data.setdefault("outlook", {})
    df = data.setdefault("defaults", {})
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
    if args.project is not None:
        df["project"] = args.project
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
    if red.get("outlook", {}).get("ics_url"):
        red["outlook"]["ics_url"] = "***"
    print(json.dumps(red, ensure_ascii=False, indent=2))
    return 0


def _cmd_config_doctor(args: argparse.Namespace) -> int:
    if not read_raw():
        print("FAIL: sem config. Rode /clockify-setup.")
        return 1
    try:
        # use_dotenv=False: o doctor valida o config XDG + env, sem puxar um .env de cwd.
        cfg = load_config(use_dotenv=False)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1

    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    try:
        ids = {w["id"] for w in client.list_workspaces()}
    except httpx.HTTPError as e:
        status = f" (HTTP {e.response.status_code})" if isinstance(e, httpx.HTTPStatusError) else ""
        print(f"FAIL: API key inválida ou sem acesso{status}.")
        return 1
    if cfg.workspace_id in ids:
        print("OK: API key e workspace válidos.")
    else:
        print(f"FAIL: workspace '{cfg.workspace_id}' não está entre os seus workspaces.")
        return 1

    d = load_defaults()
    if d.task_name is None and d.tag_name is None:
        print("OK: sem atividade padrão (aprendo pelas suas atividades).")
    else:
        try:
            md = client.get_metadata()
        except httpx.HTTPError:
            print("WARN: erro ao buscar metadata para validar a atividade padrão.")
        else:
            if d.task_name is not None:
                task_names = {name for (_pid, name) in md.tasks}
                if d.task_name in task_names:
                    print(f"OK: tarefa default '{d.task_name}' existe.")
                else:
                    print(f"WARN: tarefa default '{d.task_name}' não encontrada no workspace.")
            if d.tag_name is not None:
                if d.tag_name in md.tags:
                    print(f"OK: etiqueta default '{d.tag_name}' existe.")
                else:
                    print(f"WARN: etiqueta default '{d.tag_name}' não encontrada.")

    if cfg.ics_url:
        try:
            # GET (não HEAD): endpoints ICS do Outlook respondem 405 a HEAD mas 200 a GET —
            # é o mesmo método que o `agenda` usa para buscar a agenda de verdade.
            httpx.get(cfg.ics_url, timeout=10.0, follow_redirects=True).raise_for_status()
            print("OK: link ICS acessível.")
        except httpx.HTTPError:
            print("WARN: link ICS não respondeu (necessário só para /lancar).")
    else:
        print("WARN: ICS não configurado (necessário só para /lancar).")
    return 0


def _cmd_learned_list(args: argparse.Namespace) -> int:
    print(json.dumps(learned.read_learned(), ensure_ascii=False, indent=2))
    return 0


def _cmd_learned_add(args: argparse.Namespace) -> int:
    learned.record(
        match=args.match,
        project_name=args.project,
        task_name=args.task,
        tag_names=[args.tag] if args.tag else [],
        billable=bool(args.billable) if args.billable is not None else False,
    )
    print(f"Atividade aprendida: {args.match}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clockify-plugin")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_agenda = sub.add_parser("agenda", help="Lê a agenda do Outlook (ICS) de um dia")
    p_agenda.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_agenda.set_defaults(func=_cmd_agenda)

    p_meta = sub.add_parser("meta", help="Lista projetos/tarefas/tags do workspace")
    p_meta.set_defaults(func=_cmd_meta)

    p_ws = sub.add_parser("workspaces", help="Lista os workspaces da conta (precisa só da api key)")
    p_ws.set_defaults(func=_cmd_workspaces)

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
    p_set.add_argument("--project")
    bill = p_set.add_mutually_exclusive_group()
    bill.add_argument("--billable", dest="billable", action="store_const", const=True, default=None)
    bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_set.set_defaults(func=_cmd_config_set)

    p_path = config_sub.add_parser("path", help="Imprime o caminho do arquivo de config")
    p_path.set_defaults(func=_cmd_config_path)

    p_show = config_sub.add_parser("show", help="Imprime a config (api_key redigida)")
    p_show.set_defaults(func=_cmd_config_show)

    p_doc = config_sub.add_parser("doctor", help="Valida a config contra a API")
    p_doc.set_defaults(func=_cmd_config_doctor)

    p_learned = sub.add_parser("learned", help="Atividades aprendidas (memória local)")
    learned_sub = p_learned.add_subparsers(dest="learned_cmd", required=True)

    p_ll = learned_sub.add_parser("list", help="Lista as atividades aprendidas (JSON)")
    p_ll.set_defaults(func=_cmd_learned_list)

    p_la = learned_sub.add_parser("add", help="Aprende uma atividade por palavra-chave")
    p_la.add_argument("--match", required=True, help="Palavra-chave ou título a reconhecer")
    p_la.add_argument("--task", required=True)
    p_la.add_argument("--tag")
    p_la.add_argument("--project")
    la_bill = p_la.add_mutually_exclusive_group()
    la_bill.add_argument(
        "--billable", dest="billable", action="store_const", const=True, default=None
    )
    la_bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_la.set_defaults(func=_cmd_learned_add)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
