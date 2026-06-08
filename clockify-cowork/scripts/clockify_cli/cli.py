"""Dispatch do CLI. Cada subcomando imprime JSON em stdout (idioma-neutro) e
retorna um código de saída (0 = ok, !=0 = erro). A skill conversacional
interpreta o JSON; o CLI nunca escreve frase pronta pro usuário."""

import argparse
import json
import sys


def _emit(obj, stream) -> None:
    json.dump(obj, stream, ensure_ascii=False)
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clockify_cli")
    p.add_subparsers(dest="cmd")
    return p


def main(argv=None, *, stdout=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help(stdout)
        return 0
    _emit({"error": "UNKNOWN_COMMAND", "cmd": args.cmd}, stdout)
    return 2
