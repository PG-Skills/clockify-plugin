"""Lógica pura portada do v1.0 (`entries.py`/`clockify_api.py`/`bizdays.py`).

Sem IO, sem `self`: conversão de hora local -> ISO UTC, janelas UTC de um dia/intervalo
local (para as queries de time-entries) e listagem de dias úteis.
"""

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def to_utc_iso(dt: datetime) -> str:
    """Datetime aware -> string ISO8601 em UTC com sufixo Z (formato do Clockify)."""
    if dt.tzinfo is None:
        raise ValueError("datetime precisa ser aware (com timezone)")
    return dt.astimezone(timezone.utc).strftime(_UTC_FMT)


def day_window_utc(target_date: date, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` em ISO UTC que cobre o dia local `target_date`.

    O dia local 00:00–24:00 é convertido para instantes UTC — evita tratar 00:00–23:59
    local como se fosse UTC (que em UTC-3 perderia 3h do dia).
    """
    day_start = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(
        timezone.utc
    )
    day_end = day_start + timedelta(days=1)
    return day_start.strftime(_UTC_FMT), day_end.strftime(_UTC_FMT)


def range_window_utc(start: date, end: date, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` em ISO UTC cobrindo o intervalo local `[start, end]` (inclusive).

    00:00 local de `start` até 00:00 local do dia seguinte a `end`, convertido para UTC.
    """
    win_start = datetime.combine(start, time.min, tzinfo=tz).astimezone(timezone.utc)
    win_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(
        timezone.utc
    )
    return win_start.strftime(_UTC_FMT), win_end.strftime(_UTC_FMT)


def business_days(start: date, end: date) -> list[date]:
    """Lista as datas seg–sex no intervalo [start, end] (inclusive).

    Não filtra feriados — isso é podado manualmente na conversa. ValueError se start > end.
    """
    if start > end:
        raise ValueError(f"start ({start}) não pode ser depois de end ({end})")
    dias: list[date] = []
    atual = start
    while atual <= end:
        if atual.weekday() < 5:  # 0=seg ... 4=sex; 5=sáb, 6=dom
            dias.append(atual)
        atual += timedelta(days=1)
    return dias


def month_window_utc(year: int, month: int, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` ISO UTC cobrindo o mês LOCAL (year, month): 00:00 do dia 1
    até 00:00 do dia 1 do mês seguinte, em UTC."""
    first = datetime(year, month, 1, tzinfo=tz)
    nxt = (
        datetime(year + 1, 1, 1, tzinfo=tz)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=tz)
    )
    return (
        first.astimezone(timezone.utc).strftime(_UTC_FMT),
        nxt.astimezone(timezone.utc).strftime(_UTC_FMT),
    )


def _entry_seconds(entry: dict) -> float:
    """Duração (segundos) de um time-entry cru; 0 se faltar start/end (entry em aberto)."""
    ti = entry.get("timeInterval") or {}
    start, end = ti.get("start"), ti.get("end")
    if not start or not end:
        return 0.0
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return max(0.0, (e - s).total_seconds())


def _entry_local_dt(entry: dict, tz: ZoneInfo) -> datetime | None:
    """Início do entry em hora LOCAL (para agrupar por dia/mês local)."""
    start = (entry.get("timeInterval") or {}).get("start")
    if not start:
        return None
    return datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(tz)


def total_hours(entries: list[dict]) -> float:
    """Total de horas (2 casas) somando as durações brutas (evita drift de arredondamento)."""
    return round(sum(_entry_seconds(e) for e in entries) / 3600, 2)


def hours_by_day(entries: list[dict], tz: ZoneInfo) -> list[dict]:
    """`[{date, hours}]` por dia LOCAL (só dias com horas > 0), ordenado por data."""
    acc: dict[str, float] = {}
    for e in entries:
        dt = _entry_local_dt(e, tz)
        secs = _entry_seconds(e)
        if dt is None or secs <= 0:
            continue
        acc[dt.date().isoformat()] = acc.get(dt.date().isoformat(), 0.0) + secs
    return [{"date": k, "hours": round(v / 3600, 2)} for k, v in sorted(acc.items())]


def hours_by_month(entries: list[dict], tz: ZoneInfo) -> list[dict]:
    """`[{month "YYYY-MM", hours}]` por mês LOCAL (só meses com horas > 0), ordenado."""
    acc: dict[str, float] = {}
    for e in entries:
        dt = _entry_local_dt(e, tz)
        secs = _entry_seconds(e)
        if dt is None or secs <= 0:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}"
        acc[key] = acc.get(key, 0.0) + secs
    return [{"month": k, "hours": round(v / 3600, 2)} for k, v in sorted(acc.items())]


def _project_label(entry: dict) -> str | None:
    """Nome do projeto de um entry. Lê `project.name` (resposta hidratada); se ausente,
    cai para `projectId` (não funde projetos distintos quando a hidratação falha). `None`
    quando não há projeto algum -> a skill verbaliza 'Sem projeto'."""
    proj = entry.get("project")
    if isinstance(proj, dict):
        return proj.get("name") or entry.get("projectId")
    return entry.get("projectId")


def hours_by_project(entries: list[dict]) -> list[dict]:
    """`[{project, hours}]` agregado por projeto, ordenado por horas desc (depois nome).
    Entradas em aberto (sem end) são ignoradas. Projeto desconhecido -> `project: None`."""
    acc: dict[str, list] = {}  # key -> [label, segundos]
    for e in entries:
        secs = _entry_seconds(e)
        if secs <= 0:
            continue
        label = _project_label(e)
        key = (
            label if label is not None else "\x00sem"
        )  # bucket único para "sem projeto"
        if key not in acc:
            acc[key] = [label, 0.0]
        acc[key][1] += secs
    out = [{"project": lbl, "hours": round(s / 3600, 2)} for lbl, s in acc.values()]
    out.sort(key=lambda d: (-d["hours"], d["project"] or ""))
    return out


def business_day_gaps(year: int, month: int, logged_dates, today: date) -> list[str]:
    """Dias úteis (seg–sex) do mês (year, month) SEM lançamento e **anteriores a hoje**.

    `logged_dates`: datas ISO ('YYYY-MM-DD') que já têm horas. `today`: data local atual
    (injetada -> função pura). O corte `< today` cobre os dois casos: mês passado (todos os
    dias úteis entram) e mês corrente (só os já vencidos; não cobra o próprio dia de hoje).
    Não conhece feriados — a skill avisa para conferir."""
    logged = set(logged_dates)
    first = date(year, month, 1)
    last = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    ) - timedelta(days=1)
    return [
        d.isoformat()
        for d in business_days(first, last)
        if d < today and d.isoformat() not in logged
    ]


def summary_days(days: list[dict]) -> dict:
    """Resumo do modo diário a partir de `days` ([{date, hours}]): nº de dias lançados,
    média por dia lançado e o dia mais cheio. Lista vazia -> zeros e `max_day: None`."""
    if not days:
        return {"days_logged": 0, "avg_hours": 0.0, "max_day": None}
    total = sum(d["hours"] for d in days)
    mx = max(days, key=lambda d: d["hours"])
    return {
        "days_logged": len(days),
        "avg_hours": round(total / len(days), 2),
        "max_day": {"date": mx["date"], "hours": mx["hours"]},
    }


def summary_months(months: list[dict]) -> dict:
    """Resumo do modo mensal a partir de `months` ([{month, hours}]): nº de meses com horas,
    média por mês e o mês mais cheio. Lista vazia -> zeros e `max_month: None`."""
    if not months:
        return {"months_logged": 0, "avg_hours": 0.0, "max_month": None}
    total = sum(m["hours"] for m in months)
    mx = max(months, key=lambda m: m["hours"])
    return {
        "months_logged": len(months),
        "avg_hours": round(total / len(months), 2),
        "max_month": {"month": mx["month"], "hours": mx["hours"]},
    }
