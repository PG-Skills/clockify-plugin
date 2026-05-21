# CLAUDE.md

Wrapper fino para o Claude Code neste repositório. Detalhes de uso ficam no `README.md`.

## Comandos principais

```bash
uv sync                       # instalar deps
uv run pytest -q              # testes
uv run ruff check .           # lint
uv run pyright                # type check
uv run clockify-horas --help  # CLI
```

## Arquitetura

CLI fina (`clockify-horas`) que lê a agenda do Outlook (ICS) e grava lançamentos no
Clockify via API REST. Separação **cérebro / IO**: o slash command orquestra a conversa,
a CLI só executa I/O confiável.

- `cli.py` — subcomandos `agenda`, `meta`, `entries` (`--date` ou `--start/--end`), `business-days`, `add` (`--dry-run`).
- `ics.py` — fetch + parse do ICS, **expande recorrências** (`recurring-ical-events`) e ignora `STATUS:CANCELLED`.
- `clockify_api.py` — client HTTP (base `https://api.clockify.me/api/v1`), metadata paginada, entries por dia/intervalo, create.
- `entries.py` — lógica pura: `from_event`, totais, `to_utc_iso`, `build_payload` (resolve nomes → IDs).
- `bizdays.py` — dias úteis (seg–sex) de um intervalo. `config.py` — `.env` + `defaults.json`. `models.py` — dataclasses.
- Slash commands: `.claude/commands/horas.md` (um dia via Outlook), `.claude/commands/lancar.md` (vários dias / retroativo).

## Convenções específicas (gotchas)

- **Tarefa resolve por NOME, globalmente** (`build_payload._resolve_task`) — o nome precisa ser único entre projetos. Default: `Time IA` / tag `Célula de Inovação` / não-faturável (`defaults.json`).
- **Overrides por cliente** vivem na auto-memória (ex: Farmacia San Pablo / Mulesoft → tarefa `Implementação Assinatura Eletrônica`, tag `Implantação`, faturável). Ver memória do projeto.
- **Horários em UTC**: o Clockify recebe `Z`; conversão de hora local (UTC-3) em `to_utc_iso`.
- **`add` é resiliente a falha parcial**: para no 1º erro, reporta "gravou N de M", sai ≠ 0. Re-rodar só com o restante (não há trava anti-duplicata no `add`).
- **Sempre dry-run antes de gravar.** Anti-duplicata = `entries` + omitir manualmente dias já lançados.

## Documentação relacionada

- `README.md` — setup e uso. `docs/superpowers/specs|plans/` — design histórico.
