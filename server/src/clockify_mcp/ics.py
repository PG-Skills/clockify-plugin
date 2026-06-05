"""Leitor de agenda Outlook (ICS) — portado do v1.0, adaptado para async.

Separação fetch/parse:
- `fetch_ics` (async, httpx.AsyncClient) baixa o ICS publicado. Usa **GET** — o endpoint
  ICS do Outlook rejeita HEAD. Espelha o estilo async de `clockify.get_user`.
- `events_for_day` é PURO (sem rede): recebe o texto do ICS e a data alvo, expande
  recorrências (RRULE/RDATE via `recurring_ical_events`) e ignora `STATUS:CANCELLED`.

Retorna `list[dict]` com `title`/`start`/`end` (datetime aware em hora local), ordenado
por início — evita acoplar a um model e mantém o resultado serializável p/ o MCP.
"""

import ipaddress
import socket
from datetime import date, datetime, time, timedelta
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import httpx
import recurring_ical_events
from icalendar import Calendar

_DEFAULT_TZ = "America/Sao_Paulo"


def _validate_ics_url(url: str) -> None:
    """Anti-SSRF: exige https e host que resolve só a IPs públicos. Levanta ValueError.

    O ``ics_url`` vem do form do usuário e é buscado server-side; sem validar scheme/host
    permitiria SSRF cega (port-scan/pivô via ``169.254...`` ou hosts internos do Docker).
    Resolve o host e rejeita qualquer endereço privado/loopback/link-local/reservado.
    """
    parts = urlsplit(url)
    if parts.scheme != "https":
        raise ValueError("ics_url precisa usar https://")
    host = parts.hostname
    if not host:
        raise ValueError("ics_url sem host")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError("ics_url: host não resolve") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("ics_url aponta para um endereço interno/privado")


async def fetch_ics(url: str, timeout: float = 30.0) -> str:
    """Baixa o conteúdo bruto do ICS publicado (GET). Levanta em status HTTP de erro.

    GET — NÃO HEAD: o endpoint ICS do Outlook rejeita HEAD. Valida a URL (anti-SSRF)
    ANTES do GET e desabilita redirects — o ICS do Outlook é URL direta, então
    ``follow_redirects=False`` impede um redirect para um alvo interno burlar a validação.
    """
    _validate_ics_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    return resp.text


def events_for_day(
    ics_text: str, target_date: date, tz: str | ZoneInfo = _DEFAULT_TZ
) -> list[dict]:
    """Eventos cujo início cai em ``target_date`` (no fuso ``tz``). Parte PURA, sem rede.

    Expande recorrências (RRULE/RDATE) e respeita EXDATE/RECURRENCE-ID via
    ``recurring_ical_events`` — essencial porque a agenda do Outlook é dominada por
    reuniões recorrentes. Ignora eventos all-day e os marcados ``STATUS:CANCELLED``.
    Retorna dicts ``{title, start, end}`` ordenados por início, em hora local.
    """
    zone = ZoneInfo(tz) if isinstance(tz, str) else tz
    cal = Calendar.from_ical(ics_text)
    day_start = datetime.combine(target_date, time.min, tzinfo=zone)
    day_end = day_start + timedelta(days=1)
    ocorrencias = recurring_ical_events.of(cal).between(day_start, day_end)

    eventos: list[dict] = []
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
        start_local = _to_local(start_dt, zone)
        end_local = _to_local(end_dt, zone)
        if start_local.date() != target_date:
            continue  # ocorrência que cruza a meia-noite vinda do dia anterior
        eventos.append(
            {
                "title": str(comp.get("SUMMARY", "")),
                "start": start_local,
                "end": end_local,
            }
        )
    eventos.sort(key=lambda e: e["start"])
    return eventos


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    """Garante datetime aware no fuso local."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
