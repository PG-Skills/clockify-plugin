"""Leitor de agenda Outlook (ICS) — ZERO-DEPENDÊNCIA (stdlib).

fetch/parse separados:
- validate_ics_url / fetch_ics: anti-SSRF (https + IP público), GET via urllib SEM seguir
  redirects, cap de tamanho.
- events_for_day: PURO. Parser próprio de VEVENT + expansão de recorrência comum
  (DAILY/WEEKLY/MONTHLY) por checagem por-data. Ignora CANCELLED e all-day.

Compat Python 3.10: nada de datetime.UTC; datetimes construídos campo-a-campo.
Recorrências raras podem escapar — a confirmação humana (dry-run) é a rede de segurança.
"""

import calendar
import ipaddress
import re
import socket
import urllib.request
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DEFAULT_TZ = "America/Sao_Paulo"
_MAX_BYTES = 5 * 1024 * 1024

_WINDOWS_TZ = {
    "E. South America Standard Time": "America/Sao_Paulo",
    "SA Eastern Standard Time": "America/Fortaleza",
    "UTC": "UTC",
    "GMT Standard Time": "Europe/London",
    "Eastern Standard Time": "America/New_York",
    "Central Standard Time": "America/Chicago",
    "Pacific Standard Time": "America/Los_Angeles",
    "W. Europe Standard Time": "Europe/Berlin",
    "Romance Standard Time": "Europe/Paris",
}
_WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


# ---- anti-SSRF + fetch ------------------------------------------------------


def validate_ics_url(url: str) -> None:
    """Anti-SSRF: exige https e host que resolve só a IPs públicos. ValueError se não."""
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # não seguir redirects (anti-SSRF)


def fetch_ics(url: str, timeout: float = 30.0) -> str:
    """Baixa o texto do ICS (GET, sem seguir redirects). Valida a URL antes."""
    validate_ics_url(url)
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(url, headers={"User-Agent": "clockify-plugin"})
    # Sem redirect: 3xx/4xx/5xx já levantam HTTPError (subclasse de OSError) aqui — só 2xx
    # chega a ler. O redirect NÃO é seguido (anti-SSRF).
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read(_MAX_BYTES + 1)
    if len(raw) > _MAX_BYTES:
        raise ValueError("ics muito grande")
    return raw.decode("utf-8", "replace")


# ---- parse de baixo nível ---------------------------------------------------


def _unfold(text: str) -> list:
    raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = []
    for ln in raw:
        if ln[:1] in (" ", "\t") and lines:
            lines[-1] += ln[1:]
        else:
            lines.append(ln)
    return lines


def _split_prop(line: str):
    # 1º ':' FORA de aspas (params podem ser "...:..." citados, ex.: TZID="GMT+05:30")
    in_q = False
    idx = -1
    for i, ch in enumerate(line):
        if ch == '"':
            in_q = not in_q
        elif ch == ":" and not in_q:
            idx = i
            break
    if idx == -1:
        return None
    left, value = line[:idx], line[idx + 1 :]
    segs = left.split(";")
    params = {}
    for seg in segs[1:]:
        if "=" in seg:
            k, v = seg.split("=", 1)
            params[k.upper()] = v.strip('"')
    return segs[0].upper(), params, value


def _unescape(text: str) -> str:
    out = []
    i = 0
    table = {"n": "\n", "N": "\n", ",": ",", ";": ";", "\\": "\\"}
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            out.append(table.get(text[i + 1], text[i + 1]))
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _resolve_tz(tzid, local):
    if not tzid:
        return local
    try:
        return ZoneInfo(tzid)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        mapped = _WINDOWS_TZ.get(tzid)
        if mapped:
            try:
                return ZoneInfo(mapped)
            except Exception:
                return local
        return local


def _parse_dt(value, params, local):
    """Retorna (datetime_aware, is_all_day)."""
    v = value.strip()
    if params.get("VALUE", "").upper() == "DATE" or (len(v) == 8 and "T" not in v):
        return datetime(int(v[0:4]), int(v[4:6]), int(v[6:8]), tzinfo=local), True
    z = v.endswith("Z")
    core = v[:-1] if z else v
    y, mo, d = int(core[0:4]), int(core[4:6]), int(core[6:8])
    hh = int(core[9:11])
    mm = int(core[11:13])
    ss = int(core[13:15]) if len(core) >= 15 else 0
    if z:
        return datetime(y, mo, d, hh, mm, ss, tzinfo=timezone.utc), False
    return datetime(
        y, mo, d, hh, mm, ss, tzinfo=_resolve_tz(params.get("TZID"), local)
    ), False


def _parse_duration(s: str) -> timedelta:
    s = s.strip()
    wk = re.fullmatch(r"[+-]?P(\d+)W", s)  # semanas são exclusivas das outras unidades
    if wk:
        return timedelta(weeks=int(wk.group(1)))
    m = re.fullmatch(r"[+-]?P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?", s)
    if not m:
        return timedelta()
    d, h, mi, sec = (int(x) if x else 0 for x in m.groups())
    return timedelta(days=d, hours=h, minutes=mi, seconds=sec)


def _parse_vevents(lines):
    events = []
    cur = None
    for line in lines:
        up = line.strip().upper()
        if up == "BEGIN:VEVENT":
            cur = {"_exdate": []}
        elif up == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
        elif cur is not None:
            parsed = _split_prop(line)
            if not parsed:
                continue
            name, params, value = parsed
            if name == "EXDATE":
                cur["_exdate"].append((params, value))
            else:
                cur[name] = (params, value)
    return events


def _parse_rrule(value):
    out = {}
    for part in value.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.upper()] = v.upper()
    return out


# ---- recorrência por-data ---------------------------------------------------


def _occurs_on(d0: date, rrule: dict, cand: date) -> bool:
    """cand casa o padrão (sem COUNT/UNTIL/EXDATE)?"""
    if cand < d0:
        return False
    freq = rrule.get("FREQ", "")
    interval = max(
        1, int(rrule.get("INTERVAL", "1") or "1")
    )  # INTERVAL 0/ausente -> 1 (anti ZeroDivision)
    if freq == "DAILY":
        return (cand - d0).days % interval == 0
    if freq == "WEEKLY":
        byday = rrule.get("BYDAY")
        days = (
            {_WEEKDAYS[x] for x in byday.split(",") if x in _WEEKDAYS}
            if byday
            else {d0.weekday()}
        )
        if cand.weekday() not in days:
            return False
        mon0 = d0 - timedelta(days=d0.weekday())
        monc = cand - timedelta(days=cand.weekday())
        return ((monc - mon0).days // 7) % interval == 0
    if freq == "MONTHLY":
        bmd = rrule.get("BYMONTHDAY")
        if bmd and bmd.lstrip("-").isdigit():
            n = int(bmd)
            # negativo conta do fim do mês: -1 = último dia
            day = calendar.monthrange(cand.year, cand.month)[1] + n + 1 if n < 0 else n
        else:
            day = d0.day
        if cand.day != day:
            return False
        months = (cand.year - d0.year) * 12 + (cand.month - d0.month)
        return months >= 0 and months % interval == 0
    return cand == d0  # FREQ não suportado -> só a base


def _within_count(d0: date, rrule: dict, cand: date) -> bool:
    count = rrule.get("COUNT")
    if not count:
        return True
    count = int(count)
    if rrule.get("FREQ") == "DAILY":
        interval = max(1, int(rrule.get("INTERVAL", "1") or "1"))
        return ((cand - d0).days // interval) < count
    seen = 0
    cur = d0
    cap = 100000
    while cur <= cand and seen < count and cap > 0:
        if _occurs_on(d0, rrule, cur):
            if cur == cand:
                return True
            seen += 1
        cur += timedelta(days=1)
        cap -= 1
    return False


def _until_dt(rrule, local):
    """UNTIL como datetime aware (UTC se 'Z'), p/ comparar com o INÍCIO da ocorrência.
    Colapsar pra data perderia até um dia em UNTIL ...T000000Z (muito comum no Outlook)."""
    u = rrule.get("UNTIL")
    if not u:
        return None
    dt, _ = _parse_dt(u, {}, local)
    return dt


def _exdate_dates(exdate_list, local):
    out = set()
    for params, value in exdate_list:
        for v in value.split(","):
            dt, _ = _parse_dt(v, params, local)
            out.add(dt.date())
    return out


def _override_dates_by_uid(events, local):
    """Datas (por UID) que têm um VEVENT de override (RECURRENCE-ID). A série master
    NÃO deve gerar ocorrência nessas datas — o override é a verdade daquele dia.
    Sem isso, remarcar UMA ocorrência no Outlook duplica o dia: fantasma no horário
    antigo (master não suprimido) + a entrada remarcada (override)."""
    out = {}
    for ev in events:
        rid, uid = ev.get("RECURRENCE-ID"), ev.get("UID")
        if not rid or not uid:
            continue
        try:
            dt, _ = _parse_dt(rid[1], rid[0], local)
        except (ValueError, KeyError):
            continue
        out.setdefault(uid[1].strip(), set()).add(dt.date())
    return out


# ---- API pública ------------------------------------------------------------


def events_for_day(ics_text, target_date, tz=_DEFAULT_TZ):
    local = ZoneInfo(tz) if isinstance(tz, str) else tz
    evs = _parse_vevents(_unfold(ics_text))
    overrides = _override_dates_by_uid(evs, local)
    out = []
    for ev in evs:
        try:
            ov = frozenset()
            if "RECURRENCE-ID" not in ev and "UID" in ev:
                # só a série master é suprimida nas datas de override; o override em si não
                ov = overrides.get(ev["UID"][1].strip(), frozenset())
            out.extend(_event_occurrences(ev, target_date, local, ov))
        except (ValueError, KeyError):
            continue  # VEVENT malformado: pula só ele, não aborta a agenda inteira
    out.sort(key=lambda e: e["start"])
    return out


def _event_occurrences(ev, target_date, local, override_dates=frozenset()):
    if "DTSTART" not in ev:
        return []
    if "STATUS" in ev and ev["STATUS"][1].strip().upper() == "CANCELLED":
        return []
    start_dt, all_day = _parse_dt(ev["DTSTART"][1], ev["DTSTART"][0], local)
    if all_day:
        return []
    if "DTEND" in ev:
        end_dt, end_all_day = _parse_dt(ev["DTEND"][1], ev["DTEND"][0], local)
        if end_all_day:
            return []
        duration = end_dt - start_dt
    elif "DURATION" in ev:
        duration = _parse_duration(ev["DURATION"][1])
    else:
        return []
    title = _unescape(ev["SUMMARY"][1]) if "SUMMARY" in ev else ""
    d0 = start_dt.date()

    until_dt = None
    occ_dates = []
    if "RRULE" in ev:
        rrule = _parse_rrule(ev["RRULE"][1])
        until_dt = _until_dt(rrule, local)
        exdates = _exdate_dates(ev["_exdate"], local)
        for delta in (-1, 0, 1):
            cand = target_date + timedelta(days=delta)
            if cand < d0:
                continue
            if not _occurs_on(d0, rrule, cand):
                continue
            if not _within_count(d0, rrule, cand):
                continue
            if cand in exdates or cand in override_dates:
                continue
            occ_dates.append(cand)
    else:
        occ_dates.append(d0)

    res = []
    for cand in occ_dates:
        occ_start = start_dt.replace(year=cand.year, month=cand.month, day=cand.day)
        if until_dt is not None and occ_start > until_dt:  # UNTIL inclusivo (datetime)
            continue
        occ_end = occ_start + duration
        start_local = occ_start.astimezone(local)
        end_local = occ_end.astimezone(local)
        if start_local.date() != target_date:
            continue
        res.append({"title": title, "start": start_local, "end": end_local})
    return res
