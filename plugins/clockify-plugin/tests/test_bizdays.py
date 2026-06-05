from datetime import date

import pytest

from clockify_plugin.bizdays import business_days


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
