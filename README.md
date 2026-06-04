# clockify-horas

Plugin do Claude Code para lançar horas no Clockify a partir da agenda do Outlook (ICS).
Cada pessoa pluga as próprias credenciais e defaults — não há dado de ninguém no repo.

## Instalação

No Claude Code:

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-horas@pg-clockify
/clockify-setup
```

- `/clockify-setup` configura sua API key do Clockify, o link ICS do Outlook e seus
  defaults (tarefa/etiqueta/faturável). A CLI Python se instala sozinha na primeira sessão
  (requer [`uv`](https://docs.astral.sh/uv/)).
- Funciona em **macOS, Windows e Linux**. A única dependência é o **`uv`** —
  **não precisa ter Python instalado** (o `uv` baixa um Python gerenciado sozinho). Instalar `uv`:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Se você não tiver `uv`, o `/clockify-setup` se oferece para instalá-lo.
- Sua config fica em `~/.config/clockify-horas/config.json` (macOS/Linux) ou
  `%APPDATA%\clockify-horas\config.json` (Windows) — só sua, fora do repo.

## Uso

- `/horas` (ou `/horas 2026-01-28`) — lança um dia a partir da agenda do Outlook.
- `/lancar` — lança vários dias de uma vez (ex: mês retroativo). Funciona sem ICS.

## CLI direta

```bash
clockify-horas config show
clockify-horas config doctor
clockify-horas agenda --date 2026-01-28
clockify-horas workspaces
clockify-horas meta
clockify-horas entries --date 2026-01-28
clockify-horas business-days --start 2026-05-01 --end 2026-05-31
clockify-horas add --file lancamentos.json --dry-run
clockify-horas learned list
```

## Config (gerada pelo /clockify-setup)

Local: `~/.config/clockify-horas/config.json` (macOS/Linux) ou
`%APPDATA%\clockify-horas\config.json` (Windows).

A **atividade padrão** (`defaults`) é **opcional**: quem atua em vários clientes sem uma
tarefa dominante pode pular no `/clockify-setup` — o plugin aprende sozinho. As **atividades
aprendidas** (título/palavra-chave → projeto/tarefa) ficam em
`~/.config/clockify-horas/learned.json` (ou `%APPDATA%`), só local: o `add` aprende a cada
lançamento e o `/horas`/`/lancar` reconhecem as atividades recorrentes. A resolução de tarefa
pode ser qualificada por **projeto** (`config set --project`, `learned add --project`, ou
`project_name` no item do `add`) — necessário quando o mesmo nome de tarefa existe em vários
projetos.

```json
{
  "clockify": { "api_key": "...", "workspace_id": "..." },
  "outlook":  { "ics_url": "..." },
  "defaults": { "task_name": "...", "tag_name": "...", "billable": false, "daily_target_hours": 8.0 }
}
```

Variáveis de ambiente (`CLOCKIFY_API_KEY`, `CLOCKIFY_WORKSPACE_ID`, `OUTLOOK_ICS_URL`) têm
precedência sobre o arquivo (útil em CI).

## Dev

```bash
cd plugins/clockify-horas
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
```

Mantenedor: ver `MAINTAINER.md`.
