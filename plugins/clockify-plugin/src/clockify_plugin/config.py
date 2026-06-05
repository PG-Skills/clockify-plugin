import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = "clockify-plugin"


@dataclass
class Config:
    api_key: str
    workspace_id: str
    ics_url: str


@dataclass
class Defaults:
    task_name: str | None = None
    tag_name: str | None = None
    billable: bool | None = None
    daily_target_hours: float = 8.0
    project: str | None = None


def config_root() -> Path:
    """Diretório da config por SO. ``$XDG_CONFIG_HOME`` tem prioridade em qualquer SO."""
    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_DIR
    if os.name == "nt" and os.getenv("APPDATA"):
        return Path(os.environ["APPDATA"]) / APP_DIR
    return Path.home() / ".config" / APP_DIR


def config_path() -> Path:
    return config_root() / "config.json"


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


def load_config(use_dotenv: bool = True, path: Path | None = None) -> Config:
    """Carrega credenciais. Precedência: variável de ambiente > arquivo de config.

    ICS é opcional (só usado pelo subcomando ``agenda``). ``use_dotenv=False`` pula a
    leitura do .env nos testes.
    """
    if use_dotenv:
        load_dotenv()
    data = read_raw(path)
    ck = data.get("clockify", {})
    ol = data.get("outlook", {})
    api_key = os.getenv("CLOCKIFY_API_KEY") or ck.get("api_key", "")
    workspace_id = os.getenv("CLOCKIFY_WORKSPACE_ID") or ck.get("workspace_id", "")
    ics_url = os.getenv("OUTLOOK_ICS_URL") or ol.get("ics_url", "")
    missing = [
        name
        for name, val in (
            ("CLOCKIFY_API_KEY", api_key),
            ("CLOCKIFY_WORKSPACE_ID", workspace_id),
        )
        if not val
    ]
    if missing:
        raise ValueError(f"Configuração faltando: {', '.join(missing)}. Rode /clockify-setup.")
    return Config(api_key=api_key, workspace_id=workspace_id, ics_url=ics_url)


def load_api_key(use_dotenv: bool = True, path: Path | None = None) -> str:
    """Carrega apenas a api key. Precedência: env > arquivo de config.

    Não exige workspace_id — útil no onboarding antes de descobrir o workspace.
    """
    if use_dotenv:
        load_dotenv()
    api_key = os.getenv("CLOCKIFY_API_KEY") or read_raw(path).get("clockify", {}).get("api_key", "")
    if not api_key:
        raise ValueError("Configuração faltando: CLOCKIFY_API_KEY. Rode /clockify-setup.")
    return api_key


def load_defaults(path: Path | None = None) -> Defaults:
    """Lê a atividade padrão. Tolerante: sem 'defaults' ou parcial → campos None + 8h.

    Não levanta por campos ausentes/parciais (a atividade padrão é opcional).
    Valores com tipo inválido (ex.: daily_target_hours não-numérico) ainda podem levantar.
    """
    d = read_raw(path).get("defaults", {})
    billable = d.get("billable")
    dth = d.get("daily_target_hours")
    return Defaults(
        task_name=d.get("task_name"),
        tag_name=d.get("tag_name"),
        billable=bool(billable) if billable is not None else None,
        daily_target_hours=float(dth) if dth is not None else 8.0,
        project=d.get("project"),
    )
