from datetime import UTC, datetime

from clockify_horas.config import Defaults
from clockify_horas.models import CalEvent, Metadata, TimeEntry

_TOLERANCE_HOURS = 0.25  # 15 min de folga antes de avisar


def from_event(event: CalEvent, defaults: Defaults) -> TimeEntry:
    """Converte uma reunião do calendário num lançamento aplicando os defaults."""
    return TimeEntry(
        description=event.title,
        start=event.start,
        end=event.end,
        task_name=defaults.task_name,
        tag_names=[defaults.tag_name],
        billable=defaults.billable,
    )


def duration_hours(entry: TimeEntry) -> float:
    return (entry.end - entry.start).total_seconds() / 3600


def day_total_hours(entries: list[TimeEntry]) -> float:
    return sum(duration_hours(e) for e in entries)


def target_warning(total: float, target: float) -> str | None:
    """Mensagem de aviso se o total do dia foge do alvo além da tolerância; senão None."""
    if abs(total - target) <= _TOLERANCE_HOURS:
        return None
    rel = "abaixo" if total < target else "acima"
    return f"Total do dia: {total:g}h ({rel} da meta de {target:g}h)."


def to_utc_iso(dt: datetime) -> str:
    """Datetime aware -> string ISO8601 em UTC com sufixo Z (formato do Clockify)."""
    if dt.tzinfo is None:
        raise ValueError("datetime precisa ser aware (com timezone)")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_payload(entry: TimeEntry, metadata: Metadata) -> dict:
    """Resolve nomes -> IDs e monta o corpo do POST de time-entry do Clockify.

    Levanta KeyError com o nome ofensor se a tarefa ou alguma tag não existir
    na metadata (o CLI/orquestrador deve listar os disponíveis e pedir correção).
    """
    project_id, task_id = _resolve_task(entry.task_name, metadata)
    tag_ids = [_resolve_tag(name, metadata) for name in entry.tag_names]
    return {
        "start": to_utc_iso(entry.start),
        "end": to_utc_iso(entry.end),
        "description": entry.description,
        "projectId": project_id,
        "taskId": task_id,
        "tagIds": tag_ids,
        "billable": entry.billable,
    }


def _resolve_task(task_name: str, metadata: Metadata) -> tuple[str, str]:
    matches = [(pid, tid) for (pid, name), tid in metadata.tasks.items() if name == task_name]
    if not matches:
        raise KeyError(f"Tarefa não encontrada no Clockify: {task_name!r}")
    if len(matches) > 1:
        proj_by_id = {pid: pname for pname, pid in metadata.projects.items()}
        projs = ", ".join(proj_by_id.get(pid, pid) for pid, _ in matches)
        raise KeyError(
            f"Tarefa {task_name!r} ambígua: existe em múltiplos projetos ({projs}). "
            "Renomeie para um nome único entre projetos."
        )
    return matches[0]


def _resolve_tag(tag_name: str, metadata: Metadata) -> str:
    try:
        return metadata.tags[tag_name]
    except KeyError:
        raise KeyError(f"Etiqueta não encontrada no Clockify: {tag_name!r}") from None
