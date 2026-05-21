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
uv run clockify-horas entries --date 2026-01-28
uv run clockify-horas add --file lancamentos.json --dry-run
```
