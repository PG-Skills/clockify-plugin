#!/usr/bin/env python3
"""Instala/atualiza a CLI clockify-horas com guard de versão. Roda em SessionStart.
Cross-platform (macOS/Windows/Linux). Sempre sai 0 para nunca bloquear a sessão.
Invocado via `uv run --script` — só requer `uv` no PATH.
"""

# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _log(msg: str) -> None:
    print(f"clockify-horas: {msg}", file=sys.stderr)


def main() -> int:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return 0
    data = os.environ.get("CLAUDE_PLUGIN_DATA") or str(Path.home() / ".cache" / "clockify-horas")
    Path(data).mkdir(parents=True, exist_ok=True)
    stamp = Path(data) / "cli-version"

    # C2: versão = o campo que o mantenedor faz bump no plugin.json (fonte única).
    try:
        manifest = json.loads(
            (Path(root) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        version = str(manifest.get("version", "0"))
    except (OSError, json.JSONDecodeError):
        version = "0"

    if shutil.which("uv") is None:
        _log("'uv' não encontrado — rode /clockify-setup para instruções de instalação.")
        return 0

    fresh = (
        stamp.exists()
        and stamp.read_text(encoding="utf-8").strip() == version
        and shutil.which("clockify-horas") is not None
    )
    if fresh:
        return 0

    try:
        subprocess.run(["uv", "tool", "install", "--force", root], check=True)
        stamp.write_text(version, encoding="utf-8")
        _log(f"CLI {version} instalada/atualizada.")
    except subprocess.CalledProcessError:
        _log("falha ao instalar a CLI — rode /clockify-setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
