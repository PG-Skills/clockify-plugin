"""Dispatch do CLI. Cada subcomando imprime JSON em stdout (idioma-neutro) e
retorna um código de saída (0=ok, 2=cmd desconhecido/items inválidos, 3=sem chave,
4=chave inválida, 5=erro de rede/HTTP). A skill conversacional interpreta o JSON; o CLI
nunca escreve frase pronta pro usuário."""

import argparse
import json
import sys

import clockify
import config
import http_json
import prefs as prefs_mod
import pure
import resolve as resolve_mod

EXIT_OK, EXIT_UNKNOWN, EXIT_NO_KEY, EXIT_INVALID_KEY, EXIT_HTTP = 0, 2, 3, 4, 5
_REQUIRED_ITEM_KEYS = {"date", "start", "end", "task"}


def _emit(obj, stream) -> None:
    json.dump(obj, stream, ensure_ascii=False)
    stream.write("\n")


def _load_key(stdout):
    creds = config.load_credentials()
    if not creds or not creds.get("api_key"):
        _emit({"error": "NO_KEY"}, stdout)
        return None
    return creds


def _account(creds, stdout):
    """(workspace_id, user_id) a partir do cache; só chama get_user se faltar algum
    (e re-cacheia). Mantém o caminho quente (entries/add/resolve) SEM rede quando a conta
    já foi resolvida no whoami/conexão (spec §4). Se PRECISAR chamar get_user e a chave for
    inválida (401/403), emite INVALID_KEY e retorna None — o chamador devolve
    EXIT_INVALID_KEY em vez de estourar traceback (cache incompleto + chave ruim)."""
    ws, uid = creds.get("workspace_id"), creds.get("user_id")
    if ws and uid:
        return ws, uid
    try:
        user = clockify.get_user(creds["api_key"])
    except ValueError:
        _emit({"error": "INVALID_KEY"}, stdout)
        return None
    config.save_credentials(
        api_key=creds["api_key"],
        ics_url=creds.get("ics_url"),
        workspace_id=user["workspace_id"],
        user_id=user["id"],
    )
    return user["workspace_id"], user["id"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clockify_cli")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("whoami")

    bd = sub.add_parser("business-days")
    bd.add_argument("--start", required=True)
    bd.add_argument("--end", required=True)

    en = sub.add_parser("entries")
    en.add_argument("--date")
    en.add_argument("--start")
    en.add_argument("--end")

    rs = sub.add_parser("resolve")
    rs.add_argument("--name", required=True)
    rs.add_argument("--project")
    rs.add_argument("--tag")

    ad = sub.add_parser("add")
    ad.add_argument("--json", required=True, help="'-' para ler de stdin")
    ad.add_argument("--dry-run", action="store_true")

    pr = sub.add_parser("prefs")
    prs = pr.add_subparsers(dest="prefs_cmd")
    prs.add_parser("get")
    prs.add_parser("reset")
    sd = prs.add_parser("set-default")
    for f in ("project", "task", "tag"):
        sd.add_argument(f"--{f}")
    sd.add_argument("--billable", action=argparse.BooleanOptionalAction)
    sd.add_argument("--daily-target", type=float)
    ln = prs.add_parser("learn")
    ln.add_argument("--match", required=True)
    ln.add_argument("--project", required=True)
    for f in ("task", "tag"):
        ln.add_argument(f"--{f}")
    ln.add_argument("--billable", action=argparse.BooleanOptionalAction)
    fg = prs.add_parser("forget")
    fg.add_argument("--match", required=True)
    return p


def main(argv=None, *, stdout=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)

    if not args.cmd:
        build_parser().print_help(stdout)
        return EXIT_OK

    try:
        if args.cmd == "whoami":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            try:
                user = clockify.get_user(creds["api_key"])
            except ValueError:
                _emit({"error": "INVALID_KEY"}, stdout)
                return EXIT_INVALID_KEY
            config.save_credentials(
                api_key=creds["api_key"],
                ics_url=creds.get("ics_url"),
                workspace_id=user["workspace_id"],
                user_id=user["id"],
            )
            _emit(
                {
                    "name": user["name"],
                    "email": user["email"],
                    "workspace_id": user["workspace_id"],
                },
                stdout,
            )
            return EXIT_OK

        if args.cmd == "business-days":
            from datetime import date

            dias = pure.business_days(
                date.fromisoformat(args.start), date.fromisoformat(args.end)
            )
            _emit({"days": [d.isoformat() for d in dias]}, stdout)
            return EXIT_OK

        if args.cmd == "entries":
            from datetime import date
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("America/Sao_Paulo")
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, uid = acct
            if args.date:
                win_start, win_end = pure.day_window_utc(
                    date.fromisoformat(args.date), tz
                )
            else:
                win_start, win_end = pure.range_window_utc(
                    date.fromisoformat(args.start), date.fromisoformat(args.end), tz
                )
            out = clockify.entries(creds["api_key"], ws, uid, win_start, win_end)
            _emit({"entries": out}, stdout)
            return EXIT_OK

        if args.cmd == "resolve":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, _uid = acct
            out = resolve_mod.resolve_activity(
                creds["api_key"], ws, name=args.name, project=args.project, tag=args.tag
            )
            _emit(out, stdout)
            return EXIT_OK

        if args.cmd == "add":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            raw = (
                sys.stdin.read()
                if args.json == "-"
                else open(args.json, encoding="utf-8").read()
            )
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                _emit({"error": "INVALID_ITEMS", "reason": "json_malformado"}, stdout)
                return EXIT_UNKNOWN
            if not isinstance(items, list):
                _emit({"error": "INVALID_ITEMS", "reason": "esperava_lista"}, stdout)
                return EXIT_UNKNOWN
            bad = [
                i
                for i, it in enumerate(items)
                if not isinstance(it, dict) or not _REQUIRED_ITEM_KEYS <= set(it)
            ]
            if bad:
                _emit({"error": "INVALID_ITEMS", "missing_at": bad}, stdout)
                return EXIT_UNKNOWN
            if args.dry_run:
                _emit({"dry_run": True, "items": items}, stdout)
                return EXIT_OK
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, uid = acct
            out = resolve_mod.add_entries(creds["api_key"], ws, uid, items)
            _emit(out, stdout)
            return EXIT_OK

        if args.cmd == "prefs":
            if args.prefs_cmd == "get":
                _emit(prefs_mod.get_prefs(), stdout)
            elif args.prefs_cmd == "reset":
                prefs_mod.clear()
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "set-default":
                prefs_mod.set_default(
                    project=args.project,
                    task=args.task,
                    tag=args.tag,
                    billable=args.billable,
                    daily_target=args.daily_target,
                )
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "learn":
                prefs_mod.learn(
                    args.match,
                    project=args.project,
                    task=args.task,
                    tag=args.tag,
                    billable=args.billable,
                )
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "forget":
                _emit(
                    {"ok": True, "removed": prefs_mod.forget_learned(args.match)},
                    stdout,
                )
            else:
                _emit({"error": "UNKNOWN_COMMAND", "cmd": "prefs"}, stdout)
                return EXIT_UNKNOWN
            return EXIT_OK

        _emit({"error": "UNKNOWN_COMMAND", "cmd": args.cmd}, stdout)
        return EXIT_UNKNOWN

    except http_json.HttpError as e:
        _emit({"error": "HTTP_ERROR", "status": e.status}, stdout)
        return EXIT_HTTP
