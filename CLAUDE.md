# CLAUDE.md

Wrapper fino para o Claude Code neste repositório. Detalhes de uso ficam no `README.md`.

## Comandos principais

Rodar dentro de `plugins/clockify-horas/`:

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
- `bizdays.py` — dias úteis (seg–sex) de um intervalo. `config.py` — config XDG + precedência env. `models.py` — dataclasses.
- Slash commands: `plugins/clockify-horas/commands/horas.md` (um dia via Outlook), `plugins/clockify-horas/commands/lancar.md` (vários dias / retroativo).

## Convenções específicas (gotchas)

- **Config por-usuário** em `~/.config/clockify-horas/config.json` (macOS/Linux) ou
  `%APPDATA%\clockify-horas\config.json` (Windows); `$XDG_CONFIG_HOME` tem prioridade.
  Variáveis de ambiente têm precedência sobre o arquivo (CI/testes). Criada/editada via
  `/clockify-setup` ou o subcomando `clockify-horas config set`.
- **Tarefa resolve por NOME, globalmente** (`build_payload._resolve_task`) — o nome precisa
  ser único entre projetos.
- **Atividades aprendidas** (título/palavra-chave → projeto/tarefa) vivem em
  `learned.json` por-usuário (fora do repo): o `add` aprende no sucesso e `learned add`
  registra por palavra-chave. O **Claude** reconhece na conversa; o código não adivinha.
  Não há dado de cliente no repo.
- **ICS é opcional**: só o subcomando `agenda` (fluxo `/horas`) precisa dele; `/lancar`
  funciona sem.
- **Horários em UTC**: conversão de hora local (America/Sao_Paulo) em `to_utc_iso`.
- **`add` é resiliente a falha parcial**: para no 1º erro, reporta "gravou N de M", sai ≠ 0.
- **Sempre dry-run antes de gravar.** Anti-duplicata = `entries` + omitir dias já lançados.

## Documentação relacionada

- `README.md` — setup e uso. `docs/superpowers/specs|plans/` — design histórico.
