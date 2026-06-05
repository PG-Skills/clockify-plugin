"""Lógica pura portada do v1.0 (`entries.py`/`clockify_api.py`/`bizdays.py`).

Sem IO, sem `self`: conversão de hora local -> ISO UTC, janelas UTC de um dia/intervalo
local (para as queries de time-entries) e listagem de dias úteis.
"""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"


def to_utc_iso(dt: datetime) -> str:
    """Datetime aware -> string ISO8601 em UTC com sufixo Z (formato do Clockify)."""
    if dt.tzinfo is None:
        raise ValueError("datetime precisa ser aware (com timezone)")
    return dt.astimezone(UTC).strftime(_UTC_FMT)


def day_window_utc(target_date: date, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` em ISO UTC que cobre o dia local `target_date`.

    O dia local 00:00–24:00 é convertido para instantes UTC — evita tratar 00:00–23:59
    local como se fosse UTC (que em UTC-3 perderia 3h do dia).
    """
    day_start = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(UTC)
    day_end = day_start + timedelta(days=1)
    return day_start.strftime(_UTC_FMT), day_end.strftime(_UTC_FMT)


def range_window_utc(start: date, end: date, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` em ISO UTC cobrindo o intervalo local `[start, end]` (inclusive).

    00:00 local de `start` até 00:00 local do dia seguinte a `end`, convertido para UTC.
    """
    win_start = datetime.combine(start, time.min, tzinfo=tz).astimezone(UTC)
    win_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(
        UTC
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
