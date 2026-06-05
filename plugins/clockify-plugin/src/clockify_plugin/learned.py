import json
import os
from pathlib import Path

from clockify_plugin.config import config_root


def learned_path() -> Path:
    return config_root() / "learned.json"


def _norm(match: str) -> str:
    return match.strip().lower()


def read_learned(path: Path | None = None) -> list[dict]:
    """Lê a lista de atividades aprendidas. Ausente/corrompido/formato inesperado → []."""
    p = path or learned_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return data if isinstance(data, list) else []


def write_learned(data: list[dict], path: Path | None = None) -> Path:
    p = path or learned_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":  # chmod 600 é POSIX-only
        p.chmod(0o600)
    return p


def record(
    match: str,
    project_name: str | None,
    task_name: str,
    tag_names: list[str],
    billable: bool,
    path: Path | None = None,
) -> None:
    """Upsert de uma atividade aprendida (dedup por `match` normalizado).

    Chaves espelham o item do JSON do `add` (project_name/task_name/tag_names/billable),
    para o Claude copiar direto sem renomear campo. `match` guarda o texto original.
    """
    entry = {
        "match": match,
        "project_name": project_name,
        "task_name": task_name,
        "tag_names": list(tag_names),
        "billable": bool(billable),
    }
    data = read_learned(path)
    for i, a in enumerate(data):
        if _norm(a.get("match", "")) == _norm(match):
            data[i] = entry
            break
    else:
        data.append(entry)
    write_learned(data, path)
