from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import httpx
import recurring_ical_events
from icalendar import Calendar

from clockify_plugin.models import CalEvent


def fetch_ics(url: str, timeout: float = 30.0) -> str:
    """Baixa o conteúdo bruto do ICS publicado. Levanta em status HTTP de erro."""
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def parse_ics(ics_text: str, target_date: date, tz: ZoneInfo) -> list[CalEvent]:
    """Extrai os eventos cujo início cai em ``target_date`` (no fuso ``tz``).

    Expande recorrências (RRULE/RDATE) e respeita EXDATE/RECURRENCE-ID via
    ``recurring_ical_events`` — essencial porque a agenda do Outlook é dominada por
    reuniões recorrentes. Ignora eventos all-day e os marcados ``STATUS:CANCELLED``.
    Retorna ordenado por horário de início, em hora local.
    """
    cal = Calendar.from_ical(ics_text)
    day_start = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    ocorrencias = recurring_ical_events.of(cal).between(day_start, day_end)

    eventos: list[CalEvent] = []
    for comp in ocorrencias:
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = comp.get("DTSTART")
        end = comp.get("DTEND")
        if start is None or end is None:
            continue
        start_dt = start.dt
        end_dt = end.dt
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
            continue  # all-day event
        start_local = _to_local(start_dt, tz)
        end_local = _to_local(end_dt, tz)
        if start_local.date() != target_date:
            continue  # ocorrência que cruza a meia-noite vinda do dia anterior
        eventos.append(
            CalEvent(title=str(comp.get("SUMMARY", "")), start=start_local, end=end_local)
        )
    eventos.sort(key=lambda e: e.start)
    return eventos


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    """Garante datetime aware no fuso local."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
