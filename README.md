# clockify-horas

Lançador de horas Clockify a partir da agenda do Outlook (ICS), operado via `/horas`.

## Pré-requisitos

- Python 3.12+ e [uv](https://docs.astral.sh/uv/)
- Conta Clockify (API key) e calendário do Outlook publicado como ICS

## Setup

1. `uv sync`
2. Copie `.env.example` para `.env` e preencha:
   - `CLOCKIFY_API_KEY` — Clockify → Profile Settings → API → Generate
   - `CLOCKIFY_WORKSPACE_ID` — rode `uv run clockify-horas meta` (lista workspaces se vazio)
   - `OUTLOOK_ICS_URL` — Outlook → Calendário → Compartilhar → Publicar → link `.ics`
3. Ajuste `defaults.json` se a tarefa/etiqueta default mudar.

## Uso

No Claude Code:
- `/horas` (ou `/horas 2026-01-28`) — lança um dia a partir da agenda do Outlook.
- `/lancar` — lança em vários dias de uma vez (ex: maio retroativo).

## CLI direta

```bash
uv run clockify-horas agenda --date 2026-01-28
uv run clockify-horas meta
uv run clockify-horas entries --date 2026-01-28
uv run clockify-horas business-days --start 2026-05-01 --end 2026-05-31
uv run clockify-horas entries --start 2026-05-01 --end 2026-05-31
uv run clockify-horas add --file lancamentos.json --dry-run
```

## Estrutura

```
src/clockify_horas/
  cli.py           # subcomandos: agenda, meta, entries, business-days, add
  ics.py           # fetch + parse ICS (expande recorrências)
  clockify_api.py  # client HTTP da API Clockify
  entries.py       # lógica pura (payload, totais, UTC)
  bizdays.py       # dias úteis de um intervalo
  config.py        # .env + defaults.json
  models.py        # dataclasses
.claude/commands/  # /horas e /lancar
tests/             # pytest + respx (sem chamadas reais)
```

## Dev

```bash
uv run pytest -q       # testes
uv run ruff check .    # lint
uv run pyright         # type check
```

