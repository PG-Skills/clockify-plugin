"""Localização e leitura/escrita do estado local em `.clockify/`.

Precedência da base: CLOCKIFY_DIR (env) > $CLAUDE_PROJECT_DIR/.clockify > ./.clockify.
`credentials.json` é o único arquivo sensível (api_key); fica sob `.clockify/`,
que DEVE estar no .gitignore."""

import json
import os
from pathlib import Path

CREDENTIALS_FILE = "credentials.json"


def base_dir() -> Path:
    env = os.environ.get("CLOCKIFY_DIR")
    if env:
        return Path(env)
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".clockify"
    return Path.cwd() / ".clockify"


def _credentials_path() -> Path:
    return base_dir() / CREDENTIALS_FILE


def load_credentials() -> dict | None:
    p = _credentials_path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_credentials(
    *,
    api_key: str,
    ics_url: str | None,
    workspace_id: str | None,
    user_id: str | None = None,
) -> None:
    d = base_dir()
    d.mkdir(parents=True, exist_ok=True)
    d.chmod(0o700)  # dono-only, mesmo se a pasta já existia
    payload = {
        "api_key": api_key,
        "ics_url": ics_url,
        "workspace_id": workspace_id,
        "user_id": user_id,
    }
    p = _credentials_path()
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False, indent=2))
    p.chmod(0o600)  # idempotente: cobre arquivo pré-existente
