"""Store SQLite de preferências NÃO-sensíveis por usuário do Clockify.

A chave do Clockify NUNCA entra aqui — só metadado de conveniência (atividade
padrão e atividades aprendidas: palavra-chave → destino). Conexão por-chamada
(single-instance, leigos, sem pool/ORM); WAL; tabelas criadas no 1º uso.
"""

import sqlite3
from pathlib import Path

from .settings import get_settings

_DEFAULT_COLS = ("project", "task", "tag", "billable", "daily_target")
_LEARNED_COLS = ("project", "task", "tag", "billable")


def _norm(match: str) -> str:
    return match.strip().lower()


def _db_path() -> str:
    return get_settings().prefs_db


def _connect() -> sqlite3.Connection:
    path = _db_path()
    parent = Path(path).parent
    if str(parent) not in ("", "."):
        parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS defaults (
            user_id      TEXT PRIMARY KEY,
            project      TEXT,
            task         TEXT,
            tag          TEXT,
            billable     INTEGER,
            daily_target REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS learned (
            user_id    TEXT,
            match_norm TEXT,
            project    TEXT,
            task       TEXT,
            tag        TEXT,
            billable   INTEGER,
            PRIMARY KEY (user_id, match_norm)
        )
        """
    )
    return conn


def set_default(
    user_id: str,
    *,
    project: str | None = None,
    task: str | None = None,
    tag: str | None = None,
    billable: bool | None = None,
    daily_target: float | None = None,
) -> None:
    """Upsert da atividade padrão do usuário (uma linha por user_id)."""
    billable_int = None if billable is None else int(bool(billable))
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO defaults
                (user_id, project, task, tag, billable, daily_target)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                project      = excluded.project,
                task         = excluded.task,
                tag          = excluded.tag,
                billable     = excluded.billable,
                daily_target = excluded.daily_target
            """,
            (user_id, project, task, tag, billable_int, daily_target),
        )


def learn(
    user_id: str,
    match: str,
    *,
    project: str | None = None,
    task: str | None = None,
    tag: str | None = None,
    billable: bool | None = None,
) -> None:
    """Upsert de uma atividade aprendida (dedup por `match` normalizado).

    Last-write-wins por (user_id, match_norm), atômico via ON CONFLICT.
    """
    billable_int = None if billable is None else int(bool(billable))
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO learned
                (user_id, match_norm, project, task, tag, billable)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, match_norm) DO UPDATE SET
                project  = excluded.project,
                task     = excluded.task,
                tag      = excluded.tag,
                billable = excluded.billable
            """,
            (user_id, _norm(match), project, task, tag, billable_int),
        )


def _row_default(row: sqlite3.Row) -> dict:
    return {
        "project": row["project"],
        "task": row["task"],
        "tag": row["tag"],
        "billable": None if row["billable"] is None else bool(row["billable"]),
        "daily_target": row["daily_target"],
    }


def _row_learned(row: sqlite3.Row) -> dict:
    return {
        "match": row["match_norm"],
        "project": row["project"],
        "task": row["task"],
        "tag": row["tag"],
        "billable": None if row["billable"] is None else bool(row["billable"]),
    }


def get_prefs(user_id: str) -> dict:
    """`{"default": {...} | None, "learned": [{match,project,task,tag,billable}, ...]}`.

    User inexistente → `{"default": None, "learned": []}`.
    """
    with _connect() as conn:
        drow = conn.execute(
            "SELECT * FROM defaults WHERE user_id = ?", (user_id,)
        ).fetchone()
        lrows = conn.execute(
            "SELECT * FROM learned WHERE user_id = ? ORDER BY match_norm",
            (user_id,),
        ).fetchall()
    return {
        "default": _row_default(drow) if drow is not None else None,
        "learned": [_row_learned(r) for r in lrows],
    }
