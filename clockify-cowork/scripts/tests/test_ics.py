from datetime import date
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
    monkeypatch.setattr(
        ics.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("10.0.0.1", 0))]
    )
    with pytest.raises(ValueError):
        ics.validate_ics_url("https://internal.local/cal.ics")


def test_validate_accepts_public(monkeypatch):
    monkeypatch.setattr(
        ics.socket, "getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))]
    )
    ics.validate_ics_url("https://outlook.office365.com/x.ics")  # não levanta


# --- fetch_ics (mock urlopen via opener) ---
def test_fetch_ics_https_only():
    with pytest.raises(ValueError):
        ics.fetch_ics("http://x/y.ics")


# --- events_for_day: simples / fora / all-day / cancelled ---
def test_simple_event_on_day():
    cal = _cal(
        _ev(SUMMARY="Daily", DTSTART="20260128T120000Z", DTEND="20260128T123000Z")
    )
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
    cal = _cal(
        _ev(
            SUMMARY="Feriado",
            **{"DTSTART;VALUE=DATE": "20260128", "DTEND;VALUE=DATE": "20260129"},
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []


def test_cancelled_excluded():
    cal = _cal(
        _ev(
            SUMMARY="Cancelada",
            DTSTART="20260128T120000Z",
            DTEND="20260128T130000Z",
            STATUS="CANCELLED",
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []


# --- unfolding + escaping ---
def test_unfolding_and_escape():
    # SUMMARY dobrado em duas linhas + vírgula escapada
    # RFC 5545: o unfold remove o CRLF + 1 espaço; p/ ter "parte 2" o espaço vai ANTES da dobra.
    raw = (
        "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\n"
        "SUMMARY:Reunião com cliente\\, parte \r\n 2\r\n"
        "DTSTART:20260128T120000Z\r\nDTEND:20260128T130000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    )
    evs = ics.events_for_day(raw, date(2026, 1, 28), TZ)
    assert evs[0]["title"] == "Reunião com cliente, parte 2"


# --- timezone: TZID IANA, TZID Windows, floating ---
def test_tzid_iana():
    cal = _cal(
        _ev(
            SUMMARY="A",
            **{
                "DTSTART;TZID=America/Sao_Paulo": "20260128T090000",
                "DTEND;TZID=America/Sao_Paulo": "20260128T100000",
            },
        )
    )
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9


def test_tzid_windows_name():
    cal = _cal(
        _ev(
            SUMMARY="A",
            **{
                "DTSTART;TZID=E. South America Standard Time": "20260128T090000",
                "DTEND;TZID=E. South America Standard Time": "20260128T100000",
            },
        )
    )
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9


def test_floating_treated_local():
    cal = _cal(_ev(SUMMARY="A", DTSTART="20260128T090000", DTEND="20260128T100000"))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs[0]["start"].astimezone(TZ).hour == 9


# --- recorrência ---
def test_daily_recurrence():
    cal = _cal(
        _ev(
            SUMMARY="D",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY",
        )
    )
    assert len(ics.events_for_day(cal, date(2026, 1, 28), TZ)) == 1


def test_daily_interval():
    cal = _cal(
        _ev(
            SUMMARY="D2",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY;INTERVAL=2",
        )
    )
    assert len(ics.events_for_day(cal, date(2026, 1, 3), TZ)) == 1  # +2 dias
    assert ics.events_for_day(cal, date(2026, 1, 2), TZ) == []  # dia ímpar


def test_weekly_byday():
    # toda quarta (2026-01-07 é quarta)
    cal = _cal(
        _ev(
            SUMMARY="W",
            DTSTART="20260107T120000Z",
            DTEND="20260107T123000Z",
            RRULE="FREQ=WEEKLY;BYDAY=WE",
        )
    )
    assert len(ics.events_for_day(cal, date(2026, 1, 28), TZ)) == 1  # quarta
    assert ics.events_for_day(cal, date(2026, 1, 29), TZ) == []  # quinta


def test_monthly():
    cal = _cal(
        _ev(
            SUMMARY="M",
            DTSTART="20260115T120000Z",
            DTEND="20260115T123000Z",
            RRULE="FREQ=MONTHLY",
        )
    )
    assert len(ics.events_for_day(cal, date(2026, 3, 15), TZ)) == 1
    assert ics.events_for_day(cal, date(2026, 3, 16), TZ) == []


def test_until_bounds():
    cal = _cal(
        _ev(
            SUMMARY="U",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY;UNTIL=20260110T000000Z",
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 5), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 20), TZ) == []


def test_count_daily_exact():
    cal = _cal(
        _ev(
            SUMMARY="C",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY;COUNT=3",
        )
    )  # 01,02,03
    assert ics.events_for_day(cal, date(2026, 1, 3), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 4), TZ) == []


def test_exdate_excludes():
    cal = _cal(
        _ev(
            SUMMARY="E",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY",
            EXDATE="20260128T120000Z",
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 28), TZ) == []
    assert ics.events_for_day(cal, date(2026, 1, 27), TZ) != []


def test_unsupported_freq_falls_back_to_base():
    cal = _cal(
        _ev(
            SUMMARY="Y",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=YEARLY",
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 1), TZ) != []  # data base
    assert ics.events_for_day(cal, date(2027, 1, 1), TZ) == []  # não expande YEARLY


def test_monthly_negative_bymonthday_last_day():
    # "último dia do mês": BYMONTHDAY=-1 NÃO pode sumir com o evento
    cal = _cal(
        _ev(
            SUMMARY="LD",
            DTSTART="20260131T120000Z",
            DTEND="20260131T123000Z",
            RRULE="FREQ=MONTHLY;BYMONTHDAY=-1",
        )
    )
    assert len(ics.events_for_day(cal, date(2026, 1, 31), TZ)) == 1
    assert (
        len(ics.events_for_day(cal, date(2026, 2, 28), TZ)) == 1
    )  # fev/2026 = 28 dias
    assert ics.events_for_day(cal, date(2026, 2, 27), TZ) == []


def test_duration_weeks():
    cal = _cal(_ev(SUMMARY="W1", DTSTART="20260128T120000Z", DURATION="P1W"))
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert len(evs) == 1 and (evs[0]["end"] - evs[0]["start"]).days == 7


def test_until_midnight_z_boundary():
    # UNTIL=...T000000Z: a ocorrência ao MEIO-DIA do dia 10 (12:00Z) é > 10T00:00Z -> fora
    cal = _cal(
        _ev(
            SUMMARY="UB",
            DTSTART="20260101T120000Z",
            DTEND="20260101T123000Z",
            RRULE="FREQ=DAILY;UNTIL=20260110T000000Z",
        )
    )
    assert ics.events_for_day(cal, date(2026, 1, 9), TZ) != []
    assert ics.events_for_day(cal, date(2026, 1, 10), TZ) == []


def test_quoted_tzid_param():
    cal = _cal(
        _ev(
            SUMMARY="Q",
            **{
                'DTSTART;TZID="America/Sao_Paulo"': "20260128T090000",
                'DTEND;TZID="America/Sao_Paulo"': "20260128T100000",
            },
        )
    )
    evs = ics.events_for_day(cal, date(2026, 1, 28), TZ)
    assert evs and evs[0]["start"].astimezone(TZ).hour == 9


def test_malformed_event_skipped_not_fatal():
    good = _ev(SUMMARY="OK", DTSTART="20260128T120000Z", DTEND="20260128T123000Z")
    bad = _ev(SUMMARY="Bad", DTSTART="GARBAGE", DTEND="20260128T130000Z")
    evs = ics.events_for_day(_cal(bad, good), date(2026, 1, 28), TZ)
    assert [e["title"] for e in evs] == ["OK"]  # o ruim é pulado, não aborta a agenda


def test_interval_zero_does_not_crash():
    # INTERVAL=0 não pode estourar ZeroDivisionError (clamp -> 1) nem abortar a agenda
    bad = _ev(
        SUMMARY="Z",
        DTSTART="20260101T120000Z",
        DTEND="20260101T123000Z",
        RRULE="FREQ=DAILY;INTERVAL=0",
    )
    good = _ev(SUMMARY="OK", DTSTART="20260128T120000Z", DTEND="20260128T123000Z")
    evs = ics.events_for_day(_cal(bad, good), date(2026, 1, 28), TZ)  # não levanta
    assert "OK" in [e["title"] for e in evs]
