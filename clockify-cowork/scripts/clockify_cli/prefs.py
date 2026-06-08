"""Preferências locais (não-sensíveis) em `.clockify/prefs.json`:
atividade padrão (`default`) + atividades aprendidas (`learned`, upsert por `match`).
Espelha a semântica do prefs do servidor, mas em arquivo JSON simples."""

import json

import config

PREFS_FILE = "prefs.json"


def _path():
    return config.base_dir() / PREFS_FILE


def get_prefs() -> dict:
    p = _path()
    if not p.exists():
        return {"default": {}, "learned": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("default", {})
    data.setdefault("learned", [])
    return data


def _save(data: dict) -> None:
    d = config.base_dir()
    d.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _norm(match: str) -> str:
    """Normaliza a palavra-chave (strip + lower) — PARIDADE com server/prefs.py:_norm.
    Garante que 'Daily', 'daily' e '  daily ' colidam (dedup no learn) e sejam
    esquecíveis (forget). Sem isso, case/espaço criam duplicatas e órfãos."""
    return match.strip().lower()


def set_default(*, project, task, tag, billable, daily_target) -> None:
    data = get_prefs()
    data["default"] = _clean(
        {
            "project": project,
            "task": task,
            "tag": tag,
            "billable": billable,
            "daily_target": daily_target,
        }
    )
    _save(data)


def learn(match: str, *, project, task, tag, billable) -> None:
    data = get_prefs()
    key = _norm(match)
    entry = _clean(
        {
            "match": key,
            "project": project,
            "task": task,
            "tag": tag,
            "billable": billable,
        }
    )
    learned = [
        e for e in data["learned"] if e.get("match") != key
    ]  # upsert por match_norm
    learned.append(entry)
    data["learned"] = learned
    _save(data)


def forget_learned(match: str) -> bool:
    key = _norm(match)
    data = get_prefs()
    before = len(data["learned"])
    data["learned"] = [e for e in data["learned"] if e.get("match") != key]
    removed = len(data["learned"]) < before
    if removed:
        _save(data)
    return removed


def clear() -> None:
    _save({"default": {}, "learned": []})
