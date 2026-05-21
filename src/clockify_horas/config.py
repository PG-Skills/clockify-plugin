import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


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
