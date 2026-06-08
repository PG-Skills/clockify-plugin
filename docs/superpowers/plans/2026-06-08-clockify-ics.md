# ICS (agenda Outlook) — Implementation Plan — v1.0 final

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Adicionar leitura da agenda do Outlook (ICS) ao plugin local, **zero-dependência** (stdlib), opcional, com parser próprio que expande recorrências comuns — fechando a v1.0 (tracking + config + agenda), sem `/clockify-report`.

**Architecture:** Novo módulo `clockify_cli/ics.py` (fetch anti-SSRF via `urllib` + parser stdlib de VEVENT/recorrência). Subcomando CLI `agenda`. Skill ganha onboarding ICS opcional + uso da agenda no `/clockify-tracking`. Corrige o link da chave Clockify.

**Tech Stack:** Python 3.10+ **stdlib only** (`urllib`, `zoneinfo`, `datetime`, `socket`, `ipaddress`, `re`). pytest em dev.

---

## File Structure
```
clockify-cowork/scripts/clockify_cli/
├── ics.py            # CRIAR — fetch/validate + parser + events_for_day
└── cli.py            # MODIFICAR — subcomando `agenda`
clockify-cowork/scripts/tests/
└── test_ics.py       # CRIAR
clockify-cowork/skills/clockify-tracking/SKILL.md   # MODIFICAR (link chave, onboarding ICS, agenda)
clockify-cowork/commands/clockify.md                # MODIFICAR (link chave, status ICS)
```

---

## Task 1: `ics.py` — fetch anti-SSRF + parser stdlib + `events_for_day`

**Files:** Create `clockify_cli/ics.py`; Create `tests/test_ics.py`.

- [ ] **Step 1: Escrever os testes (falham — módulo não existe)**

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

import ics

TZ = ZoneInfo("America/Sao_Paulo")

def _cal(*vevents):
    return "BEGIN:VCALENDAR\r\n" + "".join(vevents) + "END:VCALENDAR\r\n"

def _ev(**props):
    body = "BEGIN:VEVENT\r\n"
    for k, v in props.items():
        body += f"{k}:{v}\r\n"
    return body + "END:VEVENT\r\n"


# --- validate_ics_url ---
def test_validate_rejects_http():
    with pytest.raises(ValueError):
        ics.validate_ics_url("http://example.com/cal.ics")

def test_validate_rejects_private(monkeypatch):
    monkeypatch.setattr(ics.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 0))])
    with pytest.raises(ValueError):
        ics.validate_ics_url("https://internal.local/cal.ics")

def test_validate_accepts_public(monkeypatch):
    monkeypatch.setattr(ics.socket, "getaddrinfo",
                        lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    ics.validate_ics_url("https://outlook.office365.com/x.ics")  # não levanta


# --- fetch_ics (mock urlopen via opener) ---
def test_fetch_ics_https_only():
    with pytest.raises(ValueError):
        ics.fetch_ics("http://x/y.ics")


# --- events_for_day: simples / fora / all-day / cancelled ---
def test_simple_event_on_day():
    cal = _cal(_ev(SUMMARY="Daily", DTSTART="20260128T120000Z", DTEND="20260128T123000Z"))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert len(evs) == 1
    e = evs[0]
    assert e["title"] == "Daily"
    assert e["start"].astimezone(TZ).hour == 9  # 12:00Z = 09:00 BRT
    assert e["end"].astimezone(TZ).hour == 9 and e["end"].astimezone(TZ).minute == 30

def test_event_other_day_excluded():
    cal = _cal(_ev(SUMMARY="X", DTSTART="20260127T120000Z", DTEND="20260127T130000Z"))
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []

def test_all_day_excluded():
    cal = _cal(_ev(SUMMARY="Feriado", **{"DTSTART;VALUE=DATE": "20260128", "DTEND;VALUE=DATE": "20260129"}))
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []

def test_cancelled_excluded():
    cal = _cal(_ev(SUMMARY="Cancelada", DTSTART="20260128T120000Z", DTEND="20260128T130000Z", STATUS="CANCELLED"))
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []


# --- unfolding + escaping ---
def test_unfolding_and_escape():
    # SUMMARY dobrado em duas linhas + vírgula escapada
    # RFC 5545: o unfold remove o CRLF + 1 espaço; p/ ter "parte 2" o espaço vai ANTES da dobra.
    raw = ("BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
           "SUMMARY:Reunião com cliente\\, parte \r\n 2\r\n"
           "DTSTART:20260128T120000Z\r\nDTEND:20260128T130000Z\r\n"
           "END:VEVENT\r\nEND:VCALENDAR\r\n")
    evs = ics.events_for_day(raw, date(2026, 1, 28), TZ)
    assert evs[0]["title"] == "Reunião com cliente, parte 2"


# --- timezone: TZID IANA, TZID Windows, floating ---
def test_tzid_iana():
    cal = _cal(_ev(SUMMARY="A", **{"DTSTART;TZID=America/Sao_Paulo": "20260128T090000",
                                   "DTEND;TZID=America/Sao_Paulo": "20260128T100000"}))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9

def test_tzid_windows_name():
    cal = _cal(_ev(SUMMARY="A", **{"DTSTART;TZID=E. South America Standard Time": "20260128T090000",
                                   "DTEND;TZID=E. South America Standard Time": "20260128T100000"}))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9

def test_floating_treated_local():
    cal = _cal(_ev(SUMMARY="A", DTSTART="20260128T090000", DTEND="20260128T100000"))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9


# --- recorrência ---
def test_daily_recurrence():
    cal = _cal(_ev(SUMMARY="D", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY"))
    assert len(ics.events_for_day(cal, date(2026, 1, 28), TZ)) == 1

def test_daily_interval():
    cal = _cal(_ev(SUMMARY="D2", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY;INTERVAL=2"))
    assert len(ics.events_for_day(cal, date(2026, 1, 3), TZ)) == 1   # +2 dias
    assert ics.events_for_day(cal, date(2026, 1, 2), TZ) == []       # dia ímpar

def test_weekly_byday():
    # toda quarta (2026-01-07 é quarta)
    cal = _cal(_ev(SUMMARY="W", DTSTART="20260107T120000Z", DTEND="20260107T123000Z",
                   RRULE="FREQ=WEEKLY;BYDAY=WE"))
    assert len(ics.events_for_day(cal, date(2026, 1, 28), TZ)) == 1  # quarta
    assert ics.events_for_day(cal, date(2026, 1, 29), TZ) == []      # quinta

def test_monthly():
    cal = _cal(_ev(SUMMARY="M", DTSTART="20260115T120000Z", DTEND="20260115T123000Z",
                   RRULE="FREQ=MONTHLY"))
    assert len(ics.events_for_day(cal, date(2026, 3, 15), TZ)) == 1
    assert ics.events_for_day(cal, date(2026, 3, 16), TZ) == []

def test_until_bounds():
    cal = _cal(_ev(SUMMARY="U", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY;UNTIL=20260110T000000Z"))
    assert ics.events_for_day(cal, date(2026, 1, 5), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 20), TZ) == []

def test_count_daily_exact():
    cal = _cal(_ev(SUMMARY="C", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY;COUNT=3"))  # 01,02,03
    assert ics.events_for_day(cal, date(2026, 1, 3), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 4), TZ) == []

def test_exdate_excludes():
    cal = _cal(_ev(SUMMARY="E", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY", EXDATE="20260128T120000Z"))
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []
    assert ics.events_for_day(cal, date(2026, 1, 27), TZ) != []

def test_unsupported_freq_falls_back_to_base():
    cal = _cal(_ev(SUMMARY="Y", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=YEARLY"))
    assert ics.events_for_day(cal, date(2026, 1, 1), TZ) != []   # data base
    assert ics.events_for_day(cal, date(2027, 1, 1), TZ) == []   # não expande YEARLY


def test_monthly_negative_bymonthday_last_day():
    # "último dia do mês": BYMONTHDAY=-1 NÃO pode sumir com o evento
    cal = _cal(_ev(SUMMARY="LD", DTSTART="20260131T120000Z", DTEND="20260131T123000Z",
                   RRULE="FREQ=MONTHLY;BYMONTHDAY=-1"))
    assert len(ics.events_for_day(cal, date(2026, 1, 31), TZ)) == 1
    assert len(ics.events_for_day(cal, date(2026, 2, 28), TZ)) == 1  # fev/2026 = 28 dias
    assert ics.events_for_day(cal, date(2026, 2, 27), TZ) == []


def test_duration_weeks():
    cal = _cal(_ev(SUMMARY="W1", DTSTART="20260128T120000Z", DURATION="P1W"))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert len(evs) == 1 and (evs[0]["end"] - evs[0]["start"]).days == 7


def test_until_midnight_z_boundary():
    # UNTIL=...T000000Z: a ocorrência ao MEIO-DIA do dia 10 (12:00Z) é > 10T00:00Z -> fora
    cal = _cal(_ev(SUMMARY="UB", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
                   RRULE="FREQ=DAILY;UNTIL=20260110T000000Z"))
    assert ics.events_for_day(cal, date(2026, 1, 9), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 10), TZ) == []


def test_quoted_tzid_param():
    cal = _cal(_ev(SUMMARY="Q", **{'DTSTART;TZID="America/Sao_Paulo"': "20260128T090000",
                                   'DTEND;TZID="America/Sao_Paulo"': "20260128T100000"}))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs and evs[0]["start"].astimezone(TZ).hour == 9


def test_malformed_event_skipped_not_fatal():
    good = _ev(SUMMARY="OK", DTSTART="20260128T120000Z", DTEND="20260128T123000Z")
    bad = _ev(SUMMARY="Bad", DTSTART="GARBAGE", DTEND="20260128T130000Z")
    evs = ics.events_for_day(_cal(bad, good), date(2026, 1, 28), TZ)
    assert [e["title"] for e in evs] == ["OK"]  # o ruim é pulado, não aborta a agenda


def test_interval_zero_does_not_crash():
    # INTERVAL=0 não pode estourar ZeroDivisionError (clamp -> 1) nem abortar a agenda
    bad = _ev(SUMMARY="Z", DTSTART="20260101T120000Z", DTEND="20260101T123000Z",
              RRULE="FREQ=DAILY;INTERVAL=0")
    good = _ev(SUMMARY="OK", DTSTART="20260128T120000Z", DTEND="20260128T123000Z")
    evs = ics.events_for_day(_cal(bad, good), date(2026, 1, 28), TZ)  # não levanta
    assert "OK" in [e["title"] for e in evs]
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd "clockify-cowork/scripts" && python3 -m pytest tests/test_ics.py -q`
Expected: FAIL (ModuleNotFoundError: ics).

- [ ] **Step 3: Implementar `clockify_cli/ics.py`**

```python
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
    req = urllib.request.Request(url, headers={"User-Agent": "clockify-cowork"})
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
    left, value = line[:idx], line[idx + 1:]
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
    hh = int(core[9:11]); mm = int(core[11:13]); ss = int(core[13:15]) if len(core) >= 15 else 0
    if z:
        return datetime(y, mo, d, hh, mm, ss, tzinfo=timezone.utc), False
    return datetime(y, mo, d, hh, mm, ss, tzinfo=_resolve_tz(params.get("TZID"), local)), False


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
    interval = max(1, int(rrule.get("INTERVAL", "1") or "1"))  # INTERVAL 0/ausente -> 1 (anti ZeroDivision)
    if freq == "DAILY":
        return (cand - d0).days % interval == 0
    if freq == "WEEKLY":
        byday = rrule.get("BYDAY")
        days = ({_WEEKDAYS[x] for x in byday.split(",") if x in _WEEKDAYS}
                if byday else {d0.weekday()})
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


# ---- API pública ------------------------------------------------------------

def events_for_day(ics_text, target_date, tz=_DEFAULT_TZ):
    local = ZoneInfo(tz) if isinstance(tz, str) else tz
    out = []
    for ev in _parse_vevents(_unfold(ics_text)):
        try:
            out.extend(_event_occurrences(ev, target_date, local))
        except (ValueError, KeyError):
            continue  # VEVENT malformado: pula só ele, não aborta a agenda inteira
    out.sort(key=lambda e: e["start"])
    return out


def _event_occurrences(ev, target_date, local):
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
            if cand in exdates:
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
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd "clockify-cowork/scripts" && python3 -m pytest tests/test_ics.py -q`
Expected: PASS (todos os testes, ~26).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/ics.py clockify-cowork/scripts/tests/test_ics.py
git commit -m "feat(cli): leitor ICS zero-dep (fetch anti-SSRF + parser + recorrência)"
```

---

## Task 2: subcomando `agenda` no CLI

**Files:** Modify `clockify_cli/cli.py`; add tests to `tests/test_cli.py`.

Contrato: `agenda --date YYYY-MM-DD` → sem `ics_url` na credencial: `{"ics": false, "eventos": []}`; com `ics_url`: `{"ics": true, "eventos": [{"title","start","end"}]}` (start/end ISO local). Erro de fetch/URL → `{"error":"ICS_ERROR","reason":...}` (exit `EXIT_HTTP=5`). `NO_KEY` se sem chave.

- [ ] **Step 1: Testes (falham)** — adicionar a `tests/test_cli.py`

```python
def test_agenda_no_ics_configured(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)  # sem ics_url
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 0 and out == {"ics": False, "eventos": []}


def test_agenda_with_ics(monkeypatch, tmp_path):
    import config
    import ics as ics_mod
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="KEY", ics_url="https://x/y.ics",
                            workspace_id="ws1", user_id="u1")
    monkeypatch.setattr(ics_mod, "fetch_ics", lambda url: "ICSTEXT")
    from datetime import datetime
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Sao_Paulo")
    monkeypatch.setattr(ics_mod, "events_for_day", lambda txt, d, z: [
        {"title": "Daily", "start": datetime(2026, 1, 28, 9, 0, tzinfo=tz),
         "end": datetime(2026, 1, 28, 9, 30, tzinfo=tz)}])
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 0 and out["ics"] is True
    assert out["eventos"][0]["title"] == "Daily"
    assert out["eventos"][0]["start"].startswith("2026-01-28T09:00")


def test_agenda_ics_error(monkeypatch, tmp_path):
    import config
    import ics as ics_mod
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="KEY", ics_url="https://x/y.ics",
                            workspace_id="ws1", user_id="u1")
    def boom(url):
        raise ValueError("ics_url precisa usar https://")
    monkeypatch.setattr(ics_mod, "fetch_ics", boom)
    code, out = _run(["agenda", "--date", "2026-01-28"])
    assert code == 5 and out["error"] == "ICS_ERROR"
```

- [ ] **Step 2: Rodar — falha.** `cd clockify-cowork/scripts && python3 -m pytest tests/test_cli.py -q` → FAIL.

- [ ] **Step 3: Implementar no `cli.py`**

Adicionar `import ics` aos imports planos. Registrar o subparser em `build_parser`:
```python
    ag = sub.add_parser("agenda")
    ag.add_argument("--date", required=True)
```
Adicionar o branch em `main` (antes do `prefs`):
```python
        if args.cmd == "agenda":
            from datetime import date
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            ics_url = creds.get("ics_url")
            if not ics_url:
                _emit({"ics": False, "eventos": []}, stdout)
                return EXIT_OK
            try:
                text = ics.fetch_ics(ics_url)
                from zoneinfo import ZoneInfo
                evs = ics.events_for_day(text, date.fromisoformat(args.date),
                                         ZoneInfo("America/Sao_Paulo"))
            except (ValueError, OSError) as e:
                _emit({"error": "ICS_ERROR", "reason": str(e)}, stdout)
                return EXIT_HTTP
            _emit({"ics": True, "eventos": [
                {"title": e["title"], "start": e["start"].isoformat(),
                 "end": e["end"].isoformat()} for e in evs]}, stdout)
            return EXIT_OK
```
> `urllib.error.HTTPError`/`URLError` são subclasses de `OSError`, então o `except (ValueError, OSError)` cobre falha de rede e URL inválida.

- [ ] **Step 4: Rodar — passa.** `cd clockify-cowork/scripts && python3 -m pytest -q` → tudo verde.

- [ ] **Step 5: Commit**
```bash
git add clockify-cowork/scripts/clockify_cli/cli.py clockify-cowork/scripts/tests/test_cli.py
git commit -m "feat(cli): subcomando agenda (lê ICS da credencial)"
```

---

## Task 3: Skill + commands (link da chave, onboarding ICS opcional, agenda no tracking)

**Files:** Modify `clockify-cowork/skills/clockify-tracking/SKILL.md`; Modify `clockify-cowork/commands/clockify.md`. (Sem testes unitários — validação por smoke.)

- [ ] **Step 1: Corrigir o link da chave (SKILL + clockify.md)**

Em `SKILL.md`, na seção de conexão, trocar o texto do link por:
`pego em https://app.clockify.me/manage-api-keys (Perfil → Preferências → Avançado → "Gerenciar chaves de API")`.
Em `commands/clockify.md` (Passo 2), se mencionar o caminho, usar o mesmo link.

- [ ] **Step 2: Onboarding ICS opcional (SKILL.md)** — adicionar logo após o sucesso da conexão (passo 5 da seção "Conexão"):

```markdown
6. **Agenda do Outlook (opcional).** Pergunte UMA vez, leigo: *"Quer que eu puxe sua
   agenda do Outlook pra sugerir os lançamentos? É opcional — pode pular."*
   - Se **pular**: siga normal (a pessoa dita as atividades).
   - Se **sim**: oriente: *"Abra https://outlook.cloud.microsoft/mail/options/calendar/SharedCalendars
     e use **Publicar calendário** (NÃO 'Compartilhar' — são diferentes; só o Publicar gera o
     link). Copie o link que termina em **.ics** e cole aqui."* Quando colar, **reescreva**
     `.clockify/credentials.json` mantendo a chave e preenchendo `"ics_url"` com o link
     (ferramenta de arquivo). Valide rodando `... agenda --date <hoje>`: se vier
     `{"error":"ICS_ERROR",...}`, diga em linguagem simples que o link não funcionou (confirme
     que usou *Publicar* e que é o `.ics`) e ofereça tentar de novo ou pular.
```

- [ ] **Step 3: Usar a agenda no `/clockify-tracking` (SKILL.md)** — na seção "A) Um dia", inserir antes do passo de ditar:

```markdown
1. **Agenda (se configurada).** Rode `... agenda --date AAAA-MM-DD`. Se `ics` for `true`,
   use os `eventos` (title/start/end) como ponto de partida: para cada um, escolha o destino
   pela precedência (aprendida → padrão → perguntar) e valide com `resolve --project`. Se
   `ics` for `false` ou a lista vazia, siga ditando normalmente. Avise: *"puxei o que reconheci
   da sua agenda; confira e ajuste."* (a recorrência é best-effort).
```
E na seção "B) Período", no laço por dia, mencionar o mesmo `agenda --date` por dia.

- [ ] **Step 4: `/clockify` mostra status do ICS** — em `commands/clockify.md`, no sucesso, após `prefs get`, acrescentar: rode `... agenda --date <hoje>`; se `ics` for `true`, diga "agenda do Outlook conectada"; se `false`, "agenda não conectada (opcional)". Sem despejar eventos.

- [ ] **Step 5: Commit**
```bash
git add clockify-cowork/skills/clockify-tracking/SKILL.md clockify-cowork/commands/clockify.md
git commit -m "feat(skill): onboarding ICS opcional + agenda no tracking; corrige link da chave"
```

---

## Self-Review
- **Cobertura do spec:** §2.1 ics.py → Task 1; §2.2 agenda CLI → Task 2; §2.3 onboarding + §2.4 tracking + §2.5 /clockify + I4 link → Task 3; §3 contrato do parser → Task 1 (código + testes); §4 compat/segurança → Task 1 (timezone.utc, datetimes campo-a-campo, validate_ics_url, no-redirect, cap); §5 testing → testes em cada task. ✅
- **Placeholders:** nenhum — todo passo tem código/teste completo. Sem TODOs.
- **Compat 3.10:** `timezone.utc`, datetimes campo-a-campo, sem `datetime.UTC`, sem `fromisoformat` em formato parcial. ✅
- **Consistência:** `events_for_day(text, date, tz)`, `fetch_ics(url)`, `validate_ics_url(url)` usados igual em ics.py, cli.py e testes; CLI lê `ics_url` da mesma `credentials.json` (`config.load_credentials`). ✅
- **Pós plan-critic (rodada 1):** corrigidos C1 (fixture de unfold com espaço antes da dobra), C2 (`BYMONTHDAY` negativo via `calendar.monthrange`, não some mais), W1 (UNTIL comparado como **datetime** no início da ocorrência — fronteira meia-noite-Z certa), W2 (`P1W` → 7 dias), W4 (`_split_prop` ignora `:` dentro de aspas + tira aspas do param). N1: parse por-evento em try/except (um VEVENT ruim não aborta a agenda). ✅
- **Pós plan-critic (rodada 2):** corrigido C (novo) `INTERVAL=0` → `ZeroDivisionError` que escapava do guard — `interval` clampado a `max(1, …)` em `_occurs_on`/`_within_count` (+ teste de regressão). W3 era **dead code** (urllib já levanta `HTTPError` no `opener.open` para 3xx/4xx/5xx, antes do check; redirect segue não-seguido → vira `ICS_ERROR`) — removido o check morto. Re-auditoria rodou 25→26 testes verdes em Python 3.10 e 3.12. ✅
