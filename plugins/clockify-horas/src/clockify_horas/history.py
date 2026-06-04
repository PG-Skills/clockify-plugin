import json
import os
from pathlib import Path

from clockify_horas.config import config_root


def history_path() -> Path:
    return config_root() / "history.json"


def _normalize(description: str) -> str:
    return description.strip().lower()


def read_history(path: Path | None = None) -> dict:
    p = path or history_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_history(data: dict, path: Path | None = None) -> Path:
    p = path or history_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":
        p.chmod(0o600)
    return p


def record_entry(
    description: str,
    task_name: str,
    tag_names: list[str],
    billable: bool,
    project_name: str | None,
    path: Path | None = None,
) -> None:
    data = read_history(path)
    # chaves espelham o item do JSON do `add` (project_name/task_name/tag_names/billable),
    # para a sugestão mapear direto sem renomear campo.
    data[_normalize(description)] = {
        "project_name": project_name,
        "task_name": task_name,
        "tag_names": list(tag_names),
        "billable": bool(billable),
    }
    write_history(data, path)


def suggest_for(description: str, path: Path | None = None) -> dict | None:
    return read_history(path).get(_normalize(description))
