import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = "clockify-horas"


@dataclass
class Config:
    api_key: str
    workspace_id: str
    ics_url: str


@dataclass
class Defaults:
    task_name: str
    tag_name: str
    billable: bool
    daily_target_hours: float


@dataclass
class Override:
    match: str
    task_name: str
    tag_name: str
    billable: bool


def config_path() -> Path:
    """Local da config por SO. ``$XDG_CONFIG_HOME`` tem prioridade em qualquer SO
    (usado para isolar testes); no Windows usa ``%APPDATA%``; senão ``~/.config``.
    """
    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        root = Path(base)
    elif os.name == "nt" and os.getenv("APPDATA"):
        root = Path(os.environ["APPDATA"])
    else:
        root = Path.home() / ".config"
    return root / APP_DIR / "config.json"


def read_raw(path: Path | None = None) -> dict:
    p = path or config_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_raw(data: dict, path: Path | None = None) -> Path:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":  # chmod 600 é POSIX-only
        p.chmod(0o600)
    return p


_REQUIRED = ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL")


def load_config(use_dotenv: bool = True) -> Config:
    """Carrega credenciais de .env / ambiente. Levanta ValueError se faltar alguma.

    ``use_dotenv=False`` (usado em testes) pula a leitura do arquivo .env, evitando que
    um .env local repopule variáveis que o teste removeu de propósito.
    """
    if use_dotenv:
        load_dotenv()
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise ValueError(f"Variáveis de ambiente faltando: {', '.join(missing)}")
    return Config(
        api_key=os.environ["CLOCKIFY_API_KEY"],
        workspace_id=os.environ["CLOCKIFY_WORKSPACE_ID"],
        ics_url=os.environ["OUTLOOK_ICS_URL"],
    )


def load_defaults(path: Path | str = "defaults.json") -> Defaults:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Defaults(
        task_name=data["task_name"],
        tag_name=data["tag_name"],
        billable=bool(data["billable"]),
        daily_target_hours=float(data["daily_target_hours"]),
    )
