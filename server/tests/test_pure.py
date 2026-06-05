"""Lógica pura portada do v1.0: conversão UTC, janelas de dia/intervalo, dias úteis.

Sem IO, sem `self` — espelha os casos de `test_entries.py` / `test_bizdays.py` do plugin.
"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest

from clockify_mcp.pure import (
    business_days,
    day_window_utc,
    range_window_utc,
    to_utc_iso,
)

TZ = ZoneInfo("America/Sao_Paulo")


# --- to_utc_iso (de test_entries.py) ---------------------------------------


def test_to_utc_iso_converte_local_para_utc():
    dt = datetime(2026, 1, 28, 13, 0, tzinfo=TZ)  # UTC-3
    assert to_utc_iso(dt) == "2026-01-28T16:00:00Z"


def test_to_utc_iso_exige_aware():
    with pytest.raises(ValueError, match="aware"):
        to_utc_iso(datetime(2026, 1, 28, 13, 0))


# --- janelas UTC (de test_clockify_api.py: janela do dia/intervalo) ---------


def test_day_window_utc_dia_local_em_utc_menos_3():
    # dia local 28/01 em UTC-3 -> 28/01 03:00Z até 29/01 03:00Z
    start, end = day_window_utc(date(2026, 1, 28), TZ)
    assert start == "2026-01-28T03:00:00Z"
    assert end == "2026-01-29T03:00:00Z"


def test_range_window_utc_cobre_intervalo_inclusivo():
    # 01/05 a 07/05 local -> 01/05 03:00Z até 08/05 03:00Z (end+1 dia)
    start, end = range_window_utc(date(2026, 5, 1), date(2026, 5, 7), TZ)
    assert start == "2026-05-01T03:00:00Z"
    assert end == "2026-05-08T03:00:00Z"


# --- business_days (de test_bizdays.py) ------------------------------------


def test_business_days_exclui_fim_de_semana():
    # 2026-05-01 (sex) a 2026-05-07 (qui): pula 02 (sáb) e 03 (dom)
    dias = business_days(date(2026, 5, 1), date(2026, 5, 7))
    assert dias == [
        date(2026, 5, 1),
        date(2026, 5, 4),
        date(2026, 5, 5),
        date(2026, 5, 6),
        date(2026, 5, 7),
    ]


def test_business_days_intervalo_de_um_dia_util():
    assert business_days(date(2026, 5, 4), date(2026, 5, 4)) == [date(2026, 5, 4)]


def test_business_days_um_dia_fim_de_semana_vazio():
    assert business_days(date(2026, 5, 2), date(2026, 5, 2)) == []


def test_business_days_start_depois_de_end_levanta():
    with pytest.raises(ValueError, match="start"):
        business_days(date(2026, 5, 10), date(2026, 5, 1))
