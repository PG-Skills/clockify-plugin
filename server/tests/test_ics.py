"""Leitor ICS async (portado do v1.0). Parse PURO (sem rede) + fetch async (respx).

Casos espelhados do v1.0: recorrência expandida para a data, `STATUS:CANCELLED`
ignorado, horários preservados, dia sem ocorrência -> vazio.
"""

from datetime import date
from zoneinfo import ZoneInfo

import httpx
import respx

from clockify_mcp.ics import events_for_day, fetch_ics

TZ = ZoneInfo("America/Sao_Paulo")


def test_events_for_day_expande_recorrencia_e_ignora_cancelado(sample_ics):
    # 2026-01-28 é quarta. "Daily Equipe Demo" recorre seg/qua desde 05/01 -> ocorre no dia.
    # "Reunião cancelada" (STATUS:CANCELLED) às 16h NÃO pode aparecer.
    eventos = events_for_day(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    titulos = [e["title"] for e in eventos]
    assert titulos == ["Daily Equipe Demo", "Reunião Cliente X"]  # ordenado por início


def test_events_for_day_recorrencia_preserva_horario_da_instancia(sample_ics):
    eventos = events_for_day(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    daily = eventos[0]
    assert daily["title"] == "Daily Equipe Demo"
    assert daily["start"].hour == 9 and daily["start"].minute == 0
    assert daily["start"].date() == date(
        2026, 1, 28
    )  # instância, não a série original (05/01)


def test_events_for_day_preserva_horarios(sample_ics):
    eventos = events_for_day(sample_ics, target_date=date(2026, 1, 28), tz=TZ)
    reuniao = eventos[1]
    assert reuniao["start"].hour == 13
    assert reuniao["end"].hour == 14


def test_events_for_day_dia_sem_ocorrencia_retorna_vazio(sample_ics):
    # 2026-01-30 é sexta: sem ocorrência da recorrência (seg/qua) e sem eventos avulsos.
    assert events_for_day(sample_ics, target_date=date(2026, 1, 30), tz=TZ) == []


def test_events_for_day_tz_default_sao_paulo(sample_ics):
    # tz default é America/Sao_Paulo: mesmo resultado sem passar tz explícito.
    eventos = events_for_day(sample_ics, target_date=date(2026, 1, 28))
    assert [e["title"] for e in eventos] == ["Daily Equipe Demo", "Reunião Cliente X"]


@respx.mock
async def test_fetch_ics_baixa_conteudo(sample_ics):
    url = "https://outlook.example.com/cal.ics"
    route = respx.get(url).mock(return_value=httpx.Response(200, text=sample_ics))
    assert "VCALENDAR" in await fetch_ics(url)
    # GET, não HEAD (o endpoint ICS do Outlook rejeita HEAD).
    assert route.calls.last.request.method == "GET"


@respx.mock
async def test_fetch_ics_erro_http_levanta():
    url = "https://outlook.example.com/cal.ics"
    respx.get(url).mock(return_value=httpx.Response(404))
    try:
        await fetch_ics(url)
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("esperava HTTPStatusError")
