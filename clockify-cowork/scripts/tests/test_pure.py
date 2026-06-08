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
