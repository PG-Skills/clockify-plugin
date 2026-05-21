# Lançador de Horas Clockify — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir uma CLI Python fina (`clockify-horas`) que lê a agenda do Outlook via ICS, lista metadata do Clockify e cria lançamentos de tempo via API REST, orquestrada por um slash command `/horas` que conversa com o usuário.

**Architecture:** Separação entre cérebro (Claude, via slash command) e camada de I/O confiável (CLI `clockify.py`). A CLI tem três subcomandos — `agenda` (lê ICS), `meta` (lista projetos/tarefas/tags) e `add` (cria lançamentos) — e suporta `--dry-run`. Lógica pura (parsing, totais, montagem de payload) fica isolada da rede para ser testável sem mocks de I/O.

**Tech Stack:** Python 3.12+, uv, ruff, pyright, httpx (API REST + fetch ICS), icalendar (parsing), pytest + respx (mock HTTP).

---

## File Structure

```
Clockify/
├── pyproject.toml                      # projeto uv, deps + config ruff/pyright
├── .env.example                        # template de credenciais
├── defaults.json                       # tarefa/tag/faturável/meta default
├── README.md                           # como configurar e usar
├── src/clockify_horas/
│   ├── __init__.py
│   ├── models.py                       # dataclasses: CalEvent, TimeEntry, Metadata
│   ├── config.py                       # load_config(.env) + load_defaults(json)
│   ├── ics.py                          # fetch_ics (rede) + parse_ics (puro)
│   ├── clockify_api.py                 # ClockifyClient (httpx): user, metadata, entries, create
│   ├── entries.py                      # puro: from_event, totais, build_payload, to_utc_iso
│   └── cli.py                          # argparse: agenda | meta | add ; --dry-run
├── tests/
│   ├── conftest.py                     # fixtures: sample ICS, metadata fake
│   ├── test_ics.py
│   ├── test_entries.py
│   ├── test_clockify_api.py            # respx
│   └── test_cli.py
└── .claude/commands/horas.md           # prompt de orquestração do /horas
```

Responsabilidades: `models` (formas de dados, sem lógica), `config` (carregar credenciais e defaults), `ics` (calendário), `clockify_api` (toda chamada HTTP ao Clockify num só lugar), `entries` (toda regra pura), `cli` (wiring). Arquivos que mudam juntos ficam juntos; nada de rede em `entries`/`models`.

---

## Task 1: Scaffold do projeto e toolchain

**Files:**
- Create: `pyproject.toml`
- Create: `src/clockify_horas/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Criar `pyproject.toml`**

```toml
[project]
name = "clockify-horas"
version = "0.1.0"
description = "Lançador de horas Clockify a partir do Outlook (ICS)"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27",
    "icalendar>=6.0",
    "recurring-ical-events>=3.0",
    "python-dotenv>=1.0",
]

[project.scripts]
clockify-horas = "clockify_horas.cli:main"

[dependency-groups]
dev = [
    "pytest>=8.0",
    "respx>=0.21",
    "ruff>=0.6",
    "pyright>=1.1.380",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.pyright]
include = ["src", "tests"]
typeCheckingMode = "standard"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Criar `src/clockify_horas/__init__.py`**

```python
"""Lançador de horas Clockify a partir do Outlook (ICS)."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Escrever teste de smoke `tests/test_smoke.py`**

```python
import clockify_horas


def test_package_importavel():
    assert clockify_horas.__version__ == "0.1.0"
```

- [ ] **Step 4: Sincronizar deps e rodar o teste**

Run: `uv sync && uv run pytest tests/test_smoke.py -v`
Expected: PASS — 1 passed.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/clockify_horas/__init__.py tests/test_smoke.py
git commit -m "chore: scaffold do projeto clockify-horas (uv, ruff, pyright, pytest)"
```

---

## Task 2: Modelos de dados (`models.py`)

**Files:**
- Create: `src/clockify_horas/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Escrever teste falho `tests/test_models.py`**

```python
from datetime import datetime

from clockify_horas.models import CalEvent, Metadata, TimeEntry


def test_calevent_guarda_titulo_e_intervalo():
    ev = CalEvent(
        title="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0),
        end=datetime(2026, 1, 28, 14, 0),
    )
    assert ev.title == "Reunião Cliente X"
    assert ev.end > ev.start


def test_timeentry_tem_campos_obrigatorios():
    entry = TimeEntry(
        description="Ajustes agente Spend Analysis",
        start=datetime(2026, 1, 28, 13, 0),
        end=datetime(2026, 1, 28, 16, 0),
        task_name=".Célula de Inovação: Time IA",
        tag_names=["Atividades Internas"],
        billable=False,
    )
    assert entry.task_name == ".Célula de Inovação: Time IA"
    assert entry.tag_names == ["Atividades Internas"]
    assert entry.billable is False


def test_metadata_resolve_nomes():
    md = Metadata(
        workspace_id="ws1",
        user_id="u1",
        projects={"Procurement Garage": "p1"},
        tasks={("p1", ".Célula de Inovação: Time IA"): "t1"},
        tags={"Atividades Internas": "g1"},
    )
    assert md.projects["Procurement Garage"] == "p1"
    assert md.tasks[("p1", ".Célula de Inovação: Time IA")] == "t1"
    assert md.tags["Atividades Internas"] == "g1"
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.models'`.

- [ ] **Step 3: Implementar `src/clockify_horas/models.py`**

```python
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CalEvent:
    """Evento de calendário lido do ICS."""

    title: str
    start: datetime
    end: datetime


@dataclass
class TimeEntry:
    """Um lançamento de tempo a ser criado no Clockify (horários em hora local)."""

    description: str
    start: datetime
    end: datetime
    task_name: str
    tag_names: list[str]
    billable: bool


@dataclass
class Metadata:
    """IDs do workspace Clockify, indexados por nome para resolução.

    - projects: nome do projeto -> projectId
    - tasks: (projectId, nome da tarefa) -> taskId
    - tags: nome da tag -> tagId
    """

    workspace_id: str
    user_id: str
    projects: dict[str, str] = field(default_factory=dict)
    tasks: dict[tuple[str, str], str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_models.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/models.py tests/test_models.py
git commit -m "feat: modelos de dados (CalEvent, TimeEntry, Metadata)"
```

---

## Task 3: Parsing do ICS (`ics.py` — função pura `parse_ics`)

**Files:**
- Create: `src/clockify_horas/ics.py`
- Create: `tests/conftest.py`
- Test: `tests/test_ics.py`

- [ ] **Step 1: Criar fixture de ICS em `tests/conftest.py`**

```python
import pytest

SAMPLE_ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Microsoft Corporation//Outlook//EN
BEGIN:VEVENT
UID:evt-1
SUMMARY:Reunião Cliente X
DTSTART;TZID=America/Sao_Paulo:20260128T130000
DTEND;TZID=America/Sao_Paulo:20260128T140000
END:VEVENT
BEGIN:VEVENT
UID:evt-2
SUMMARY:Daily Time IA
DTSTART;TZID=America/Sao_Paulo:20260105T090000
DTEND;TZID=America/Sao_Paulo:20260105T093000
RRULE:FREQ=WEEKLY;BYDAY=MO,WE
END:VEVENT
BEGIN:VEVENT
UID:evt-3
SUMMARY:Reunião de outro dia
DTSTART;TZID=America/Sao_Paulo:20260129T100000
DTEND;TZID=America/Sao_Paulo:20260129T110000
END:VEVENT
BEGIN:VEVENT
UID:evt-4
SUMMARY:Reunião cancelada
DTSTART;TZID=America/Sao_Paulo:20260128T160000
DTEND;TZID=America/Sao_Paulo:20260128T170000
STATUS:CANCELLED
END:VEVENT
END:VCALENDAR
"""


@pytest.fixture
def sample_ics() -> str:
    return SAMPLE_ICS
```

- [ ] **Step 2: Escrever teste falho `tests/test_ics.py`**

```python
from datetime import date
from zoneinfo import ZoneInfo

from clockify_horas.ics import parse_ics

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
```

- [ ] **Step 3: Rodar para confirmar falha**

Run: `uv run pytest tests/test_ics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.ics'`.

- [ ] **Step 4: Implementar `parse_ics` em `src/clockify_horas/ics.py`**

```python
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import recurring_ical_events
from icalendar import Calendar

from clockify_horas.models import CalEvent


def parse_ics(ics_text: str, target_date: date, tz: ZoneInfo) -> list[CalEvent]:
    """Extrai os eventos cujo início cai em ``target_date`` (no fuso ``tz``).

    Expande recorrências (RRULE/RDATE) e respeita EXDATE/RECURRENCE-ID via
    ``recurring_ical_events`` — essencial porque a agenda do Outlook é dominada por
    reuniões recorrentes. Ignora eventos all-day e os marcados ``STATUS:CANCELLED``.
    Retorna ordenado por horário de início, em hora local.
    """
    cal = Calendar.from_ical(ics_text)
    day_start = datetime.combine(target_date, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    ocorrencias = recurring_ical_events.of(cal).between(day_start, day_end)

    eventos: list[CalEvent] = []
    for comp in ocorrencias:
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = comp.get("DTSTART")
        end = comp.get("DTEND")
        if start is None or end is None:
            continue
        start_dt = start.dt
        end_dt = end.dt
        if not isinstance(start_dt, datetime) or not isinstance(end_dt, datetime):
            continue  # all-day event
        start_local = _to_local(start_dt, tz)
        end_local = _to_local(end_dt, tz)
        if start_local.date() != target_date:
            continue  # ocorrência que cruza a meia-noite vinda do dia anterior
        eventos.append(
            CalEvent(title=str(comp.get("SUMMARY", "")), start=start_local, end=end_local)
        )
    eventos.sort(key=lambda e: e.start)
    return eventos


def _to_local(dt: datetime, tz: ZoneInfo) -> datetime:
    """Garante datetime aware no fuso local."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=tz)
    return dt.astimezone(tz)
```

- [ ] **Step 5: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_ics.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_horas/ics.py tests/conftest.py tests/test_ics.py
git commit -m "feat: parsing puro de ICS filtrando eventos por data"
```

---

## Task 4: Fetch do ICS (`ics.py` — `fetch_ics` com rede)

**Files:**
- Modify: `src/clockify_horas/ics.py`
- Test: `tests/test_ics.py`

- [ ] **Step 1: Escrever teste falho com respx em `tests/test_ics.py`**

Adicionar ao final do arquivo:

```python
import httpx
import respx

from clockify_horas.ics import fetch_ics


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
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_ics.py -k fetch -v`
Expected: FAIL — `ImportError: cannot import name 'fetch_ics'`.

- [ ] **Step 3: Implementar `fetch_ics` em `src/clockify_horas/ics.py`**

Adicionar `import httpx` no topo e a função:

```python
def fetch_ics(url: str, timeout: float = 30.0) -> str:
    """Baixa o conteúdo bruto do ICS publicado. Levanta em status HTTP de erro."""
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_ics.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/ics.py tests/test_ics.py
git commit -m "feat: fetch_ics baixa ICS publicado do Outlook"
```

---

## Task 5: Lógica pura de lançamentos (`entries.py`)

**Files:**
- Create: `src/clockify_horas/entries.py`
- Test: `tests/test_entries.py`

- [ ] **Step 1: Escrever teste falho `tests/test_entries.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from clockify_horas.config import Defaults
from clockify_horas.entries import (
    day_total_hours,
    from_event,
    target_warning,
    to_utc_iso,
)
from clockify_horas.models import CalEvent, TimeEntry

TZ = ZoneInfo("America/Sao_Paulo")

DEFAULTS = Defaults(
    task_name=".Célula de Inovação: Time IA",
    tag_name="Atividades Internas",
    billable=False,
    daily_target_hours=8.0,
)


def test_from_event_aplica_defaults():
    ev = CalEvent(
        title="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0, tzinfo=TZ),
        end=datetime(2026, 1, 28, 14, 0, tzinfo=TZ),
    )
    entry = from_event(ev, DEFAULTS)
    assert entry.description == "Reunião Cliente X"
    assert entry.task_name == ".Célula de Inovação: Time IA"
    assert entry.tag_names == ["Atividades Internas"]
    assert entry.billable is False
    assert entry.start == ev.start


def test_day_total_hours_soma_duracoes():
    entries = [
        TimeEntry("a", datetime(2026, 1, 28, 9), datetime(2026, 1, 28, 11),
                  ".Célula de Inovação: Time IA", ["t"], False),
        TimeEntry("b", datetime(2026, 1, 28, 13), datetime(2026, 1, 28, 16),
                  ".Célula de Inovação: Time IA", ["t"], False),
    ]
    assert day_total_hours(entries) == 5.0


def test_target_warning_avisa_quando_abaixo():
    msg = target_warning(total=5.0, target=8.0)
    assert msg is not None
    assert "5" in msg and "8" in msg


def test_target_warning_silencia_quando_no_alvo():
    assert target_warning(total=8.0, target=8.0) is None
    assert target_warning(total=7.75, target=8.0) is None  # tolerância de 15min


def test_to_utc_iso_converte_local_para_utc():
    dt = datetime(2026, 1, 28, 13, 0, tzinfo=TZ)  # UTC-3
    assert to_utc_iso(dt) == "2026-01-28T16:00:00Z"
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_entries.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.entries'` (e `config.Defaults` ainda não existe).

- [ ] **Step 3: Implementar `src/clockify_horas/entries.py`**

```python
from datetime import UTC, datetime

from clockify_horas.config import Defaults
from clockify_horas.models import CalEvent, TimeEntry

_TOLERANCE_HOURS = 0.25  # 15 min de folga antes de avisar


def from_event(event: CalEvent, defaults: Defaults) -> TimeEntry:
    """Converte uma reunião do calendário num lançamento aplicando os defaults."""
    return TimeEntry(
        description=event.title,
        start=event.start,
        end=event.end,
        task_name=defaults.task_name,
        tag_names=[defaults.tag_name],
        billable=defaults.billable,
    )


def duration_hours(entry: TimeEntry) -> float:
    return (entry.end - entry.start).total_seconds() / 3600


def day_total_hours(entries: list[TimeEntry]) -> float:
    return sum(duration_hours(e) for e in entries)


def target_warning(total: float, target: float) -> str | None:
    """Mensagem de aviso se o total do dia foge do alvo além da tolerância; senão None."""
    if abs(total - target) <= _TOLERANCE_HOURS:
        return None
    rel = "abaixo" if total < target else "acima"
    return f"Total do dia: {total:g}h ({rel} da meta de {target:g}h)."


def to_utc_iso(dt: datetime) -> str:
    """Datetime aware -> string ISO8601 em UTC com sufixo Z (formato do Clockify)."""
    if dt.tzinfo is None:
        raise ValueError("datetime precisa ser aware (com timezone)")
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_entries.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/entries.py tests/test_entries.py
git commit -m "feat: lógica pura de lançamentos (from_event, totais, warning, utc)"
```

---

## Task 6: Configuração (`config.py`)

**Files:**
- Create: `src/clockify_horas/config.py`
- Create: `.env.example`
- Create: `defaults.json`
- Test: `tests/test_config.py`

- [ ] **Step 1: Escrever teste falho `tests/test_config.py`**

```python
import json

from clockify_horas.config import Defaults, load_config, load_defaults


def test_load_config_le_variaveis(monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "key123"
    assert cfg.workspace_id == "ws1"
    assert cfg.ics_url == "https://x/cal.ics"


def test_load_config_falta_chave_levanta(monkeypatch):
    # use_dotenv=False evita que um .env local repopule a chave deletada
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    try:
        load_config(use_dotenv=False)
    except ValueError as e:
        assert "CLOCKIFY_API_KEY" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_load_defaults_le_json(tmp_path):
    p = tmp_path / "defaults.json"
    p.write_text(json.dumps({
        "task_name": ".Célula de Inovação: Time IA",
        "tag_name": "Atividades Internas",
        "billable": False,
        "daily_target_hours": 8.0,
    }), encoding="utf-8")
    d = load_defaults(p)
    assert d == Defaults(
        task_name=".Célula de Inovação: Time IA",
        tag_name="Atividades Internas",
        billable=False,
        daily_target_hours=8.0,
    )
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.config'`.

- [ ] **Step 3: Implementar `src/clockify_horas/config.py`**

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class Config:
    api_key: str
    workspace_id: str
    ics_url: str


@dataclass
class Defaults:
    task_name: str
    tag_name: str
    billable: bool
    daily_target_hours: float


_REQUIRED = ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL")


def load_config(use_dotenv: bool = True) -> Config:
    """Carrega credenciais de .env / ambiente. Levanta ValueError se faltar alguma.

    ``use_dotenv=False`` (usado em testes) pula a leitura do arquivo .env, evitando que
    um .env local repopule variáveis que o teste removeu de propósito.
    """
    if use_dotenv:
        load_dotenv()
    missing = [k for k in _REQUIRED if not os.getenv(k)]
    if missing:
        raise ValueError(f"Variáveis de ambiente faltando: {', '.join(missing)}")
    return Config(
        api_key=os.environ["CLOCKIFY_API_KEY"],
        workspace_id=os.environ["CLOCKIFY_WORKSPACE_ID"],
        ics_url=os.environ["OUTLOOK_ICS_URL"],
    )


def load_defaults(path: Path | str = "defaults.json") -> Defaults:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return Defaults(
        task_name=data["task_name"],
        tag_name=data["tag_name"],
        billable=bool(data["billable"]),
        daily_target_hours=float(data["daily_target_hours"]),
    )
```

- [ ] **Step 4: Criar `.env.example`**

```bash
# Clockify -> Profile Settings -> API -> Generate
CLOCKIFY_API_KEY=
# Descoberto via: uv run clockify-horas meta (ele lista os workspaces se faltar)
CLOCKIFY_WORKSPACE_ID=
# Outlook -> Calendário -> Compartilhar -> Publicar -> link .ics (ICS)
OUTLOOK_ICS_URL=
```

- [ ] **Step 5: Criar `defaults.json`**

```json
{
  "task_name": ".Célula de Inovação: Time IA",
  "tag_name": "Atividades Internas",
  "billable": false,
  "daily_target_hours": 8.0
}
```

> Nota de execução: confirmar com o usuário o nome exato da tag default correlata a
> `.Célula de Inovação: Time IA` (ponto em aberto da spec) e ajustar `tag_name` antes do uso real.

- [ ] **Step 6: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS — 3 passed.

- [ ] **Step 7: Commit**

```bash
git add src/clockify_horas/config.py .env.example defaults.json tests/test_config.py
git commit -m "feat: carregamento de config (.env) e defaults (json)"
```

---

## Task 7: Cliente Clockify HTTP (`clockify_api.py`)

**Files:**
- Create: `src/clockify_horas/clockify_api.py`
- Test: `tests/test_clockify_api.py`

- [ ] **Step 1: Escrever teste falho `tests/test_clockify_api.py`**

```python
from datetime import date
from zoneinfo import ZoneInfo

import httpx
import respx

from clockify_horas.clockify_api import ClockifyClient

BASE = "https://api.clockify.me/api/v1"
TZ = ZoneInfo("America/Sao_Paulo")


def _client() -> ClockifyClient:
    return ClockifyClient(api_key="key123", workspace_id="ws1")


@respx.mock
def test_get_user_id():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    assert _client().get_user_id() == "u1"


@respx.mock
def test_get_metadata_monta_indices():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    md = _client().get_metadata()
    assert md.user_id == "u1"
    assert md.projects["Procurement Garage"] == "p1"
    assert md.tasks[("p1", ".Célula de Inovação: Time IA")] == "t1"
    assert md.tags["Atividades Internas"] == "g1"


@respx.mock
def test_get_entries_for_date_usa_janela_utc_do_dia_local():
    route = respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[{"id": "e1"}])
    )
    entries = _client().get_entries_for_date("u1", date(2026, 1, 28), TZ)
    assert entries == [{"id": "e1"}]
    # dia local 28/01 em UTC-3 -> 28/01 03:00Z até 29/01 03:00Z
    sent = route.calls.last.request
    assert sent.url.params["start"] == "2026-01-28T03:00:00Z"
    assert sent.url.params["end"] == "2026-01-29T03:00:00Z"


@respx.mock
def test_get_metadata_pagina_ate_pagina_incompleta():
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(return_value=httpx.Response(200, json=[]))
    md = _client().get_metadata()
    # 1 projeto (< page-size) encerra a paginação em uma página só
    assert list(md.projects) == ["Procurement Garage"]


@respx.mock
def test_create_entry_envia_payload():
    route = respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "new1"})
    )
    payload = {"start": "2026-01-28T16:00:00Z", "description": "x"}
    resp = _client().create_entry(payload)
    assert resp["id"] == "new1"
    assert route.called
    sent = route.calls.last.request
    assert sent.headers["X-Api-Key"] == "key123"
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_clockify_api.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.clockify_api'`.

- [ ] **Step 3: Implementar `src/clockify_horas/clockify_api.py`**

```python
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from clockify_horas.models import Metadata

BASE_URL = "https://api.clockify.me/api/v1"
_PAGE_SIZE = 200


class ClockifyClient:
    """Wrapper fino sobre a API REST do Clockify. Toda chamada HTTP fica aqui."""

    def __init__(self, api_key: str, workspace_id: str, base_url: str = BASE_URL) -> None:
        self.workspace_id = workspace_id
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            timeout=30.0,
        )

    def _get(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _get_all(self, path: str) -> list[dict[str, Any]]:
        """GET paginado: percorre páginas até vir uma página incompleta."""
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._get(path, params={"page": page, "page-size": _PAGE_SIZE})
            items.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return items
            page += 1

    def get_user_id(self) -> str:
        return self._get("/user")["id"]

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._get("/workspaces")

    def get_metadata(self) -> Metadata:
        ws = self.workspace_id
        user_id = self.get_user_id()
        projects_raw = self._get_all(f"/workspaces/{ws}/projects")
        projects = {p["name"]: p["id"] for p in projects_raw}
        tasks: dict[tuple[str, str], str] = {}
        for p in projects_raw:
            for t in self._get_all(f"/workspaces/{ws}/projects/{p['id']}/tasks"):
                tasks[(p["id"], t["name"])] = t["id"]
        tags = {g["name"]: g["id"] for g in self._get_all(f"/workspaces/{ws}/tags")}
        return Metadata(
            workspace_id=ws,
            user_id=user_id,
            projects=projects,
            tasks=tasks,
            tags=tags,
        )

    def get_entries_for_date(
        self, user_id: str, target_date: date, tz: ZoneInfo
    ) -> list[dict[str, Any]]:
        """Lançamentos do usuário no dia local (para checagem anti-duplicata).

        A janela é o dia local convertido para instantes UTC — evitando o erro de
        tratar 00:00–23:59 local como se fosse UTC (que em UTC-3 perderia 3h do dia).
        """
        day_start = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(UTC)
        day_end = day_start + timedelta(days=1)
        return self._get(
            f"/workspaces/{self.workspace_id}/user/{user_id}/time-entries",
            params={
                "start": day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    def create_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(
            f"/workspaces/{self.workspace_id}/time-entries", json=payload
        )
        resp.raise_for_status()
        return resp.json()
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_clockify_api.py -v`
Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/clockify_api.py tests/test_clockify_api.py
git commit -m "feat: cliente HTTP Clockify (user, metadata, entries, create)"
```

---

## Task 8: Montagem de payload com resolução de nomes (`entries.py` — `build_payload`)

**Files:**
- Modify: `src/clockify_horas/entries.py`
- Test: `tests/test_entries.py`

- [ ] **Step 1: Escrever teste falho em `tests/test_entries.py`**

Adicionar imports e testes ao final:

```python
import pytest

from clockify_horas.entries import build_payload
from clockify_horas.models import Metadata

META = Metadata(
    workspace_id="ws1",
    user_id="u1",
    projects={"Procurement Garage": "p1"},
    tasks={("p1", ".Célula de Inovação: Time IA"): "t1"},
    tags={"Atividades Internas": "g1"},
)


def _entry() -> TimeEntry:
    return TimeEntry(
        description="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0, tzinfo=TZ),
        end=datetime(2026, 1, 28, 14, 0, tzinfo=TZ),
        task_name=".Célula de Inovação: Time IA",
        tag_names=["Atividades Internas"],
        billable=False,
    )


def test_build_payload_resolve_ids_e_converte_utc():
    payload = build_payload(_entry(), META)
    assert payload == {
        "start": "2026-01-28T16:00:00Z",
        "end": "2026-01-28T17:00:00Z",
        "description": "Reunião Cliente X",
        "projectId": "p1",
        "taskId": "t1",
        "tagIds": ["g1"],
        "billable": False,
    }


def test_build_payload_tarefa_inexistente_levanta():
    entry = _entry()
    entry.task_name = "Tarefa Que Não Existe"
    with pytest.raises(KeyError, match="Tarefa Que Não Existe"):
        build_payload(entry, META)


def test_build_payload_tag_inexistente_levanta():
    entry = _entry()
    entry.tag_names = ["Tag Inexistente"]
    with pytest.raises(KeyError, match="Tag Inexistente"):
        build_payload(entry, META)
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_entries.py -k build_payload -v`
Expected: FAIL — `ImportError: cannot import name 'build_payload'`.

- [ ] **Step 3: Implementar `build_payload` em `src/clockify_horas/entries.py`**

Adicionar `from clockify_horas.models import Metadata` ao import existente e a função:

```python
def build_payload(entry: TimeEntry, metadata: Metadata) -> dict:
    """Resolve nomes -> IDs e monta o corpo do POST de time-entry do Clockify.

    Levanta KeyError com o nome ofensor se a tarefa ou alguma tag não existir
    na metadata (o CLI/orquestrador deve listar os disponíveis e pedir correção).
    """
    project_id, task_id = _resolve_task(entry.task_name, metadata)
    tag_ids = [_resolve_tag(name, metadata) for name in entry.tag_names]
    return {
        "start": to_utc_iso(entry.start),
        "end": to_utc_iso(entry.end),
        "description": entry.description,
        "projectId": project_id,
        "taskId": task_id,
        "tagIds": tag_ids,
        "billable": entry.billable,
    }


def _resolve_task(task_name: str, metadata: Metadata) -> tuple[str, str]:
    for (project_id, name), task_id in metadata.tasks.items():
        if name == task_name:
            return project_id, task_id
    raise KeyError(f"Tarefa não encontrada no Clockify: {task_name!r}")


def _resolve_tag(tag_name: str, metadata: Metadata) -> str:
    try:
        return metadata.tags[tag_name]
    except KeyError:
        raise KeyError(f"Etiqueta não encontrada no Clockify: {tag_name!r}") from None
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_entries.py -v`
Expected: PASS — 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/entries.py tests/test_entries.py
git commit -m "feat: build_payload resolve nomes para IDs e monta corpo do POST"
```

---

## Task 9: CLI (`cli.py`) — subcomandos `agenda`, `meta`, `add`

**Files:**
- Create: `src/clockify_horas/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Escrever teste falho `tests/test_cli.py`**

```python
import json
from datetime import date

import httpx
import respx

from clockify_horas.cli import main

BASE = "https://api.clockify.me/api/v1"


def _setup_env(monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")


@respx.mock
def test_agenda_imprime_json(monkeypatch, capsys, sample_ics):
    _setup_env(monkeypatch)
    respx.get("https://x/cal.ics").mock(return_value=httpx.Response(200, text=sample_ics))
    rc = main(["agenda", "--date", "2026-01-28"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert [e["title"] for e in out] == ["Daily Time IA", "Reunião Cliente X"]
    assert out[0]["start"].startswith("2026-01-28T09:00")


@respx.mock(assert_all_called=False)  # o POST é registrado mas, em dry-run, não é chamado
def test_add_dry_run_nao_posta(monkeypatch, capsys, tmp_path):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries")
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(json.dumps([{
        "description": "Reunião Cliente X",
        "start": "2026-01-28T13:00:00-03:00",
        "end": "2026-01-28T14:00:00-03:00",
        "task_name": ".Célula de Inovação: Time IA",
        "tag_names": ["Atividades Internas"],
        "billable": False,
    }]), encoding="utf-8")
    rc = main(["add", "--file", str(entries_file), "--dry-run"])
    assert rc == 0
    assert not post_route.called  # dry-run não posta
    out = capsys.readouterr().out
    assert "2026-01-28T16:00:00Z" in out  # payload convertido p/ UTC


@respx.mock
def test_add_real_posta(monkeypatch, tmp_path):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "new1"})
    )
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(json.dumps([{
        "description": "Reunião Cliente X",
        "start": "2026-01-28T13:00:00-03:00",
        "end": "2026-01-28T14:00:00-03:00",
        "task_name": ".Célula de Inovação: Time IA",
        "tag_names": ["Atividades Internas"],
        "billable": False,
    }]), encoding="utf-8")
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 0
    assert post_route.called


@respx.mock
def test_entries_lista_lancamentos_do_dia(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[
            {"id": "e1", "description": "Já lançado",
             "timeInterval": {"start": "2026-01-28T16:00:00Z", "end": "2026-01-28T17:00:00Z"}}
        ])
    )
    rc = main(["entries", "--date", "2026-01-28"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["description"] == "Já lançado"
    assert out[0]["start"] == "2026-01-28T16:00:00Z"
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.cli'`.

- [ ] **Step 3: Implementar `src/clockify_horas/cli.py`**

```python
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from clockify_horas.clockify_api import ClockifyClient
from clockify_horas.config import load_config
from clockify_horas.entries import build_payload
from clockify_horas.ics import fetch_ics, parse_ics
from clockify_horas.models import TimeEntry

_TZ = ZoneInfo("America/Sao_Paulo")


def _parse_local(value: str) -> datetime:
    """ISO8601 -> datetime aware. Se vier sem offset, assume o fuso local."""
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=_TZ)


def _cmd_agenda(args: argparse.Namespace) -> int:
    cfg = load_config()
    target = date.fromisoformat(args.date) if args.date else date.today()
    eventos = parse_ics(fetch_ics(cfg.ics_url), target_date=target, tz=_TZ)
    payload = [
        {"title": e.title, "start": e.start.isoformat(), "end": e.end.isoformat()}
        for e in eventos
    ]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_meta(args: argparse.Namespace) -> int:
    cfg = load_config()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    md = client.get_metadata()
    out = {
        "workspace_id": md.workspace_id,
        "user_id": md.user_id,
        "projects": md.projects,
        "tasks": {f"{pid} :: {name}": tid for (pid, name), tid in md.tasks.items()},
        "tags": md.tags,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def _cmd_entries(args: argparse.Namespace) -> int:
    """Lista lançamentos já existentes no dia — usado pelo /horas p/ anti-duplicata."""
    cfg = load_config()
    target = date.fromisoformat(args.date) if args.date else date.today()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    user_id = client.get_user_id()
    existentes = client.get_entries_for_date(user_id, target, _TZ)
    resumo = [
        {
            "id": e.get("id"),
            "description": e.get("description"),
            "start": e.get("timeInterval", {}).get("start"),
            "end": e.get("timeInterval", {}).get("end"),
        }
        for e in existentes
    ]
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    cfg = load_config()
    raw = json.loads(Path(args.file).read_text(encoding="utf-8"))
    entries = [
        TimeEntry(
            description=item["description"],
            start=_parse_local(item["start"]),
            end=_parse_local(item["end"]),
            task_name=item["task_name"],
            tag_names=item["tag_names"],
            billable=bool(item["billable"]),
        )
        for item in raw
    ]
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    md = client.get_metadata()
    payloads = [build_payload(e, md) for e in entries]

    if args.dry_run:
        print(json.dumps(payloads, ensure_ascii=False, indent=2))
        return 0

    for p in payloads:
        resp = client.create_entry(p)
        print(f"Lançado: {p['description']} -> {resp.get('id')}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clockify-horas")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_agenda = sub.add_parser("agenda", help="Lê a agenda do Outlook (ICS) de um dia")
    p_agenda.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_agenda.set_defaults(func=_cmd_agenda)

    p_meta = sub.add_parser("meta", help="Lista projetos/tarefas/tags do workspace")
    p_meta.set_defaults(func=_cmd_meta)

    p_entries = sub.add_parser("entries", help="Lista lançamentos existentes no dia")
    p_entries.add_argument("--date", help="AAAA-MM-DD (default: hoje)")
    p_entries.set_defaults(func=_cmd_entries)

    p_add = sub.add_parser("add", help="Cria lançamentos a partir de um JSON")
    p_add.add_argument("--file", required=True, help="Arquivo JSON com a lista de lançamentos")
    p_add.add_argument("--dry-run", action="store_true", help="Imprime payloads sem postar")
    p_add.set_defaults(func=_cmd_add)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Rodar a suíte inteira + lint + typecheck**

Run: `uv run pytest -v && uv run ruff check . && uv run pyright`
Expected: todos os testes passam, ruff sem erros, pyright sem erros.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_cli.py
git commit -m "feat: CLI com subcomandos agenda, meta, entries e add (--dry-run)"
```

---

## Task 10: Slash command `/horas` (orquestração)

**Files:**
- Create: `.claude/commands/horas.md`

> Este arquivo não é código testável por unidade — é o prompt que o Claude segue.
> Validação é manual (Task 11). O slash command chama a CLI já testada via Bash.

- [ ] **Step 1: Criar `.claude/commands/horas.md`**

````markdown
---
description: Lança horas do dia no Clockify a partir da agenda do Outlook
---

Você vai lançar as horas do dia no Clockify de forma colaborativa. O argumento opcional
`$ARGUMENTS` pode conter uma data (AAAA-MM-DD); se vazio, use hoje.

Siga EXATAMENTE este fluxo, um passo de cada vez, conversando em português:

1. **Ler a agenda.** Rode `uv run clockify-horas agenda --date <data>`. Cada evento vira
   um lançamento candidato: descrição = título do evento, horários = os do evento, e
   aplique os defaults de `defaults.json` (tarefa `.Célula de Inovação: Time IA`,
   etiqueta default, faturável default).

2. **Anti-duplicata.** Rode `uv run clockify-horas entries --date <data>`. Se a saída
   não for vazia, JÁ existem lançamentos nessa data — AVISE o usuário, mostre o que já
   existe, e pergunte se quer continuar mesmo assim antes de seguir.

3. **Trabalho avulso.** Pergunte ao usuário o que mais fez no dia além das reuniões,
   pedindo descrição e horários de início/fim. Acrescente como lançamentos.

4. **Edição colaborativa.** Mostre a lista completa em tabela (descrição, horário,
   tarefa, etiqueta, faturável, duração). Aceite ajustes em qualquer campo de qualquer
   item. Se o usuário citar tarefa/etiqueta fora dos defaults, valide contra a saída de
   `meta`; se não existir, liste as opções disponíveis e peça correção.

5. **Total do dia.** Some as durações e informe o total. Se fugir de ~8h além de 15min,
   avise (mas não bloqueie).

6. **Confirmação + dry-run.** Monte o JSON da lista, salve em arquivo temporário e rode
   `uv run clockify-horas add --file <tmp> --dry-run`. Mostre os payloads. Peça
   confirmação explícita do usuário.

7. **Gravar.** Só após o "pode lançar", rode `uv run clockify-horas add --file <tmp>`
   (sem `--dry-run`). Reporte o resumo do que foi criado.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/horas.md
git commit -m "feat: slash command /horas para orquestrar o lançamento"
```

---

## Task 11: README e validação manual end-to-end

**Files:**
- Create: `README.md`

- [ ] **Step 1: Criar `README.md`**

````markdown
# clockify-horas

Lançador de horas Clockify a partir da agenda do Outlook (ICS), operado via `/horas`.

## Setup

1. `uv sync`
2. Copie `.env.example` para `.env` e preencha:
   - `CLOCKIFY_API_KEY` — Clockify → Profile Settings → API → Generate
   - `CLOCKIFY_WORKSPACE_ID` — rode `uv run clockify-horas meta` (lista workspaces se vazio)
   - `OUTLOOK_ICS_URL` — Outlook → Calendário → Compartilhar → Publicar → link `.ics`
3. Ajuste `defaults.json` se a tarefa/etiqueta default mudar.

## Uso

No Claude Code: `/horas` (ou `/horas 2026-01-28`).

## CLI direta

```bash
uv run clockify-horas agenda --date 2026-01-28
uv run clockify-horas meta
uv run clockify-horas add --file lancamentos.json --dry-run
```
````

- [ ] **Step 2: Validação manual (checklist, executar com credenciais reais)**

- [ ] `uv run clockify-horas meta` retorna projetos/tarefas/tags reais e o `workspace_id` correto.
      **Se der HTTP 404, a URL base está errada** — confirme `https://api.clockify.me/api/v1`.
- [ ] Confirmar o nome exato da etiqueta default e atualizar `defaults.json`.
- [ ] `uv run clockify-horas agenda --date <hoje>` lista as reuniões reais do Outlook,
      **incluindo reuniões recorrentes** (dailies/syncs) — o ponto mais crítico de validar.
- [ ] Validar que o ICS expõe a agenda completa (sem omitir privados / sem atraso grave) e
      que eventos cancelados não aparecem. **Limitação conhecida:** reuniões que você
      *recusou* podem ainda aparecer (o ICS nem sempre marca PARTSTAT) — revise na edição.
- [ ] `uv run clockify-horas entries --date <hoje>` lista lançamentos já existentes (anti-duplicata).
- [ ] `/horas` num dia de teste, com `--dry-run`, mostra payloads corretos (horários em UTC `Z`).
- [ ] Lançar 1 entrada de teste real e conferir na UI do Clockify (campos, horário, faturável, tag).
- [ ] Apagar a entrada de teste do Clockify.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README com setup e uso do clockify-horas"
```

---

## Self-Review (preenchido)

**1. Spec coverage:**
- Leitura ICS do Outlook (com expansão de recorrências) → Tasks 3, 4. ✅
- Reuniões viram lançamento (descrição = título, horário real) → Task 5 `from_event`. ✅
- Trabalho avulso → Task 10 (passo 3 do `/horas`). ✅
- Tarefa default `.Célula de Inovação: Time IA` + exceções → Tasks 6 (default), 8 (resolução). ✅
- Etiquetas obrigatórias, conjunto fixo → Tasks 6 (default), 8 (resolução/validação). ✅
- Faturável toggle → Tasks 5, 8 (campo `billable`). ✅
- Horários precisos início/fim + conversão UTC → Tasks 5 (`to_utc_iso`), 8. ✅
- Meta diária ~8h, avisa sem travar → Task 5 `target_warning`, Task 10 passo 5. ✅
- Anti-duplicata → Task 7 `get_entries_for_date` + Task 9 subcomando `entries` + Task 10 passo 2. ✅
- Dry-run sempre antes → Task 9 (`--dry-run`), Task 10 passos 6-7. ✅
- Fallback colar agenda manual → coberto pela natureza conversacional do `/horas` (orquestrador aceita entrada manual se `agenda` falhar). ✅
- API key guiada → `.env.example` + README. ✅
- Setup guiado workspace id → `meta` lista workspaces, README. ✅

**Correções pós plan-critic (Gate 1):**
- 🔴→✅ URL base corrigida para `https://api.clockify.me/api/v1` (Task 7 + testes).
- 🔴→✅ Expansão de recorrências (RRULE) via `recurring-ical-events` + skip de `STATUS:CANCELLED` (Task 3); fixture e testes cobrem recorrência semanal e cancelado.
- ⚠️→✅ Anti-duplicata agora tem superfície real (subcomando `entries`) e o `/horas` o invoca.
- ⚠️→✅ Paginação nas listagens (`_get_all`) (Task 7).
- ⚠️→✅ Janela UTC correta no `get_entries_for_date` para UTC-3 (Task 7).
- ⚠️→✅ Datetimes naive localizados no `add`; `load_config(use_dotenv=False)` em testes (Tasks 6, 9).
- ⚠️→✅ `_TZ` fixo (sem fallback `None` silencioso) (Task 9).

**2. Placeholder scan:** sem TBD/TODO em código; a única nota de execução (nome exato da tag) é um valor de configuração confirmável em runtime, não lógica pendente.

**3. Type consistency:** `TimeEntry`, `Metadata`, `Config`, `Defaults` usados de forma idêntica entre tasks; `build_payload(entry, metadata)`, `from_event(event, defaults)`, `to_utc_iso(dt)`, `parse_ics(text, target_date, tz)`, `fetch_ics(url)`, `get_entries_for_date(user_id, target_date, tz)` com assinaturas consistentes em todos os pontos de uso.
