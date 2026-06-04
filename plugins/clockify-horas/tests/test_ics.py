from datetime import date
from zoneinfo import ZoneInfo

import httpx
import respx

from clockify_horas.ics import fetch_ics, parse_ics

TZ = ZoneInfo("America/Sao_Paulo")


def test_parse_ics_expande_recorrencia_e_ignora_cancelado(sample_ics):
    # 2026-01-28 é quarta. "Daily Time IA" recorre seg/qua desde 05/01 -> ocorre no dia.
    # "Reunião cancelada" (STATUS:CANCELLED) às 16h NÃO pode aparecer.
    eventos = parse_ics(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    titulos = [e.title for e in eventos]
    assert titulos == ["Daily Time IA", "Reunião Cliente X"]  # ordenado por início


def test_parse_ics_recorrencia_preserva_horario_da_instancia(sample_ics):
    eventos = parse_ics(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    daily = eventos[0]
    assert daily.title == "Daily Time IA"
    assert daily.start.hour == 9 and daily.start.minute == 0
    assert daily.start.date() == date(2026, 1, 28)  # instância, não a série original (05/01)


def test_parse_ics_preserva_horarios(sample_ics):
    eventos = parse_ics(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    reuniao = eventos[1]
    assert reuniao.start.hour == 13
    assert reuniao.end.hour == 14


def test_parse_ics_dia_sem_ocorrencia_retorna_vazio(sample_ics):
    # 2026-01-30 é sexta: sem ocorrência da recorrência (seg/qua) e sem eventos avulsos.
    assert parse_ics(sample_ics, target_date=date(2026, 1, 30), tz=TZ) == []





@respx.mock
def test_fetch_ics_baixa_conteudo(sample_ics):
    url = "https://outlook.example.com/cal.ics"
    respx.get(url).mock(return_value=httpx.Response(200, text=sample_ics))
    assert "VCALENDAR" in fetch_ics(url)


@respx.mock
def test_fetch_ics_erro_http_levanta():
    url = "https://outlook.example.com/cal.ics"
    respx.get(url).mock(return_value=httpx.Response(404))
    try:
        fetch_ics(url)
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("esperava HTTPStatusError")
