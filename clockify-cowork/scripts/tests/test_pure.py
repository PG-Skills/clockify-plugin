from datetime import date, datetime
from zoneinfo import ZoneInfo

import pure

TZ = ZoneInfo("America/Sao_Paulo")


def test_to_utc_iso_converts_local_to_utc_z():
    dt = datetime(2026, 1, 28, 9, 0, tzinfo=TZ)  # 09:00 BRT = 12:00Z
    assert pure.to_utc_iso(dt) == "2026-01-28T12:00:00Z"


def test_to_utc_iso_requires_aware():
    import pytest

    with pytest.raises(ValueError):
        pure.to_utc_iso(datetime(2026, 1, 28, 9, 0))


def test_day_window_utc_covers_local_day():
    start, end = pure.day_window_utc(date(2026, 1, 28), TZ)
    assert start == "2026-01-28T03:00:00Z"  # 00:00 BRT = 03:00Z
    assert end == "2026-01-29T03:00:00Z"


def test_range_window_utc_inclusive():
    start, end = pure.range_window_utc(date(2026, 1, 28), date(2026, 1, 30), TZ)
    assert start == "2026-01-28T03:00:00Z"
    assert end == "2026-01-31T03:00:00Z"  # 00:00 do dia seguinte a end


def test_business_days_skips_weekend():
    dias = pure.business_days(date(2026, 1, 30), date(2026, 2, 2))  # sex..seg
    assert [d.isoformat() for d in dias] == ["2026-01-30", "2026-02-02"]


def test_business_days_rejects_inverted_range():
    import pytest

    with pytest.raises(ValueError):
        pure.business_days(date(2026, 2, 2), date(2026, 1, 30))


def test_month_window_utc():
    start, end = pure.month_window_utc(2026, 6, TZ)  # junho/2026
    assert start == "2026-06-01T03:00:00Z"  # 00:00 BRT = 03:00Z
    assert end == "2026-07-01T03:00:00Z"


def test_month_window_utc_december_rolls_year():
    start, end = pure.month_window_utc(2026, 12, TZ)
    assert start == "2026-12-01T03:00:00Z"
    assert end == "2027-01-01T03:00:00Z"


def _e(start, end):
    return {"timeInterval": {"start": start, "end": end}}


def test_hours_by_day_groups_local():
    entries = [
        _e("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z"),  # 1h, dia 01 (09-10 BRT)
        _e("2026-06-01T14:00:00Z", "2026-06-01T16:00:00Z"),  # 2h, dia 01
        _e("2026-06-02T12:00:00Z", "2026-06-02T12:30:00Z"),  # 0.5h, dia 02
    ]
    assert pure.hours_by_day(entries, TZ) == [
        {"date": "2026-06-01", "hours": 3.0},
        {"date": "2026-06-02", "hours": 0.5},
    ]


def test_hours_by_month_groups_local():
    entries = [
        _e("2026-01-15T12:00:00Z", "2026-01-15T20:00:00Z"),  # 8h jan
        _e("2026-02-10T12:00:00Z", "2026-02-10T16:00:00Z"),  # 4h fev
        _e("2026-02-11T12:00:00Z", "2026-02-11T13:00:00Z"),  # 1h fev
    ]
    assert pure.hours_by_month(entries, TZ) == [
        {"month": "2026-01", "hours": 8.0},
        {"month": "2026-02", "hours": 5.0},
    ]


def test_total_hours_and_skip_open_entries():
    entries = [
        _e("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z"),  # 1h
        {"timeInterval": {"start": "2026-06-01T14:00:00Z"}},  # sem end -> ignorado
        {"timeInterval": {}},  # vazio -> ignorado
    ]
    assert pure.total_hours(entries) == 1.0
    assert pure.hours_by_day(entries, TZ) == [{"date": "2026-06-01", "hours": 1.0}]


def test_local_grouping_crosses_utc_midnight():
    # 2026-06-02T01:00:00Z = 2026-06-01 22:00 BRT -> conta no dia 01 (local)
    entries = [_e("2026-06-02T01:00:00Z", "2026-06-02T02:00:00Z")]
    assert pure.hours_by_day(entries, TZ) == [{"date": "2026-06-01", "hours": 1.0}]


# ---- Enriquecimento do report: por projeto, lacunas e resumo ----


def _ep(start, end, *, project=None, project_id=None):
    """Entry com timeInterval e, opcionalmente, `project` (hidratado) ou `projectId` (cru)."""
    e = {"timeInterval": {"start": start, "end": end}}
    if project is not None:
        e["project"] = project
    if project_id is not None:
        e["projectId"] = project_id
    return e


def test_hours_by_project_groups_by_hydrated_name():
    entries = [
        _ep(
            "2026-06-01T12:00:00Z",
            "2026-06-01T20:00:00Z",
            project={"id": "p1", "name": "San Pablo"},
        ),  # 8h
        _ep(
            "2026-06-02T12:00:00Z",
            "2026-06-02T16:00:00Z",
            project={"id": "p1", "name": "San Pablo"},
        ),  # 4h
        _ep(
            "2026-06-03T12:00:00Z",
            "2026-06-03T15:00:00Z",
            project={"id": "p2", "name": "Interno"},
        ),  # 3h
    ]
    # ordenado por horas desc
    assert pure.hours_by_project(entries) == [
        {"project": "San Pablo", "hours": 12.0},
        {"project": "Interno", "hours": 3.0},
    ]


def test_hours_by_project_no_project_is_none_bucket():
    entries = [_ep("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z")]  # sem projeto
    assert pure.hours_by_project(entries) == [{"project": None, "hours": 1.0}]


def test_hours_by_project_fallback_to_id_when_not_hydrated():
    # sem objeto `project` (hidratação ausente) -> agrupa pelo projectId p/ não fundir projetos
    entries = [_ep("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z", project_id="abc")]
    assert pure.hours_by_project(entries) == [{"project": "abc", "hours": 1.0}]


def test_hours_by_project_skips_open_entries():
    entries = [
        {"timeInterval": {"start": "2026-06-01T12:00:00Z"}, "project": {"name": "X"}}
    ]
    assert pure.hours_by_project(entries) == []


def test_business_day_gaps_past_month_all_business_days():
    today = date(2026, 6, 8)  # estamos em junho -> maio é mês passado
    gaps = pure.business_day_gaps(2026, 5, [], today)
    assert gaps[0] == "2026-05-01" and gaps[-1] == "2026-05-29"  # sex a sex
    assert "2026-05-02" not in gaps  # sábado
    assert len(gaps) == 21


def test_business_day_gaps_current_month_excludes_today_and_logged():
    today = date(2026, 6, 8)  # segunda
    logged = ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-05"]
    # úteis antes de hoje: 01,02,03,04,05 -> falta só 04 (qui)
    assert pure.business_day_gaps(2026, 6, logged, today) == ["2026-06-04"]


def test_business_day_gaps_future_month_empty():
    assert pure.business_day_gaps(2026, 7, [], date(2026, 6, 8)) == []


def test_summary_days():
    days = [
        {"date": "2026-06-01", "hours": 8.0},
        {"date": "2026-06-03", "hours": 9.0},
        {"date": "2026-06-05", "hours": 7.0},
    ]
    assert pure.summary_days(days) == {
        "days_logged": 3,
        "avg_hours": 8.0,
        "max_day": {"date": "2026-06-03", "hours": 9.0},
    }


def test_summary_days_empty():
    assert pure.summary_days([]) == {
        "days_logged": 0,
        "avg_hours": 0.0,
        "max_day": None,
    }


def test_summary_months():
    months = [
        {"month": "2026-01", "hours": 175.0},
        {"month": "2026-05", "hours": 154.5},
    ]
    assert pure.summary_months(months) == {
        "months_logged": 2,
        "avg_hours": 164.75,
        "max_month": {"month": "2026-01", "hours": 175.0},
    }


def test_summary_months_empty():
    assert pure.summary_months([]) == {
        "months_logged": 0,
        "avg_hours": 0.0,
        "max_month": None,
    }
