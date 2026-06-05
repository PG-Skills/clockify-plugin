"""Leitor ICS async (portado do v1.0). Parse PURO (sem rede) + fetch async (respx).

Casos espelhados do v1.0: recorrência expandida para a data, `STATUS:CANCELLED`
ignorado, horários preservados, dia sem ocorrência -> vazio.
"""

from datetime import date
from zoneinfo import ZoneInfo

import httpx
import respx

import pytest

import clockify_mcp.ics as ics_mod
from clockify_mcp.ics import _validate_ics_url, events_for_day, fetch_ics

TZ = ZoneInfo("America/Sao_Paulo")


def _fake_getaddrinfo(ip: str):
    """Substitui socket.getaddrinfo para resolver qualquer host ao IP dado — sem rede."""

    def _f(host, *args, **kwargs):
        import socket

        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    return _f


# --- _validate_ics_url (anti-SSRF) -----------------------------------------


def test_validate_ics_url_rejeita_http_nao_tls():
    with pytest.raises(ValueError):
        _validate_ics_url("http://outlook.office365.com/owa/cal.ics")


def test_validate_ics_url_rejeita_ip_privado(monkeypatch):
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.1"))
    with pytest.raises(ValueError):
        _validate_ics_url("https://intranet.example.com/x.ics")


def test_validate_ics_url_rejeita_link_local_metadata(monkeypatch):
    # 169.254.169.254 — endpoint de metadata de cloud (alvo clássico de SSRF).
    monkeypatch.setattr(
        ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("169.254.169.254")
    )
    with pytest.raises(ValueError):
        _validate_ics_url("https://metadata.evil.example/x.ics")


def test_validate_ics_url_rejeita_loopback(monkeypatch):
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
    with pytest.raises(ValueError):
        _validate_ics_url("https://localhost.evil.example/x.ics")


def test_validate_ics_url_aceita_host_publico(monkeypatch):
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("52.96.0.1"))
    # Não deve levantar.
    _validate_ics_url("https://outlook.office365.com/owa/calendar/abc/cal.ics")


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
async def test_fetch_ics_baixa_conteudo(sample_ics, monkeypatch):
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("52.96.0.1"))
    url = "https://outlook.example.com/cal.ics"
    route = respx.get(url).mock(return_value=httpx.Response(200, text=sample_ics))
    assert "VCALENDAR" in await fetch_ics(url)
    # GET, não HEAD (o endpoint ICS do Outlook rejeita HEAD).
    assert route.calls.last.request.method == "GET"


@respx.mock
async def test_fetch_ics_erro_http_levanta(monkeypatch):
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("52.96.0.1"))
    url = "https://outlook.example.com/cal.ics"
    respx.get(url).mock(return_value=httpx.Response(404))
    try:
        await fetch_ics(url)
    except httpx.HTTPStatusError:
        pass
    else:
        raise AssertionError("esperava HTTPStatusError")


@respx.mock
async def test_fetch_ics_nao_segue_redirect(monkeypatch):
    """Anti-SSRF: redirect para alvo interno NÃO é seguido (follow_redirects=False)."""
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("52.96.0.1"))
    url = "https://outlook.example.com/cal.ics"
    respx.get(url).mock(
        return_value=httpx.Response(
            302, headers={"location": "http://169.254.169.254/"}
        )
    )
    # raise_for_status em 3xx levanta — não seguiu o redirect para o IP interno.
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_ics(url)


async def test_fetch_ics_rejeita_url_interna_antes_do_get(monkeypatch):
    """A validação roda ANTES do GET: URL com IP privado nem chega a sair na rede."""
    monkeypatch.setattr(ics_mod.socket, "getaddrinfo", _fake_getaddrinfo("10.0.0.1"))
    with pytest.raises(ValueError):
        await fetch_ics("https://intranet.example.com/x.ics")
