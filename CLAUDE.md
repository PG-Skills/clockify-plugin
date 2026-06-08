# CLAUDE.md

Wrapper fino para o Claude Code neste repositório. Detalhes de uso ficam no `README.md`.

## Comandos principais

Rodar dentro de `clockify-cowork/scripts/`:

```bash
python3 -m pytest -q        # testes (stdlib only, sem uv)
```

## Arquitetura

Plugin `clockify-cowork/` = **skill conversacional** + **CLI Python zero-dependência** (stdlib).
Roda no Claude desktop app ("Cowork") sobre uma pasta de projeto local.
**Sem servidor, sem OAuth, sem VPS.**

- `clockify-cowork/skills/clockify-tracking/SKILL.md` — skill principal, orquestra a conversa.
- `clockify-cowork/commands/clockify-tracking.md` — comando `/clockify-tracking` (lançar um dia ou período).
- `clockify-cowork/commands/clockify.md` — comando `/clockify` (status / verificar conexão).
- `clockify-cowork/scripts/clockify_cli/` — CLI zero-dep (Python stdlib):
  - `cli.py` — subcomandos `whoami`, `entries` (`--date` ou `--start/--end`), `business-days`, `resolve`, `add` (`--dry-run`), `prefs` (`get`/`set-default`/`learn`/`forget`/`reset`).
  - `clockify.py` — client HTTP para a API Clockify (`https://api.clockify.me/api/v1`).
  - `http_json.py` — HTTP mínimo via `urllib` (sem requests).
  - `config.py` — lê/escreve `.clockify/credentials.json` no projeto (api_key + workspace_id/user_id em cache + ics_url).
  - `prefs.py` — preferências por projeto em `.clockify/prefs.json` (default projeto/tarefa/tag/billable + learned).
  - `pure.py` — lógica pura: janelas UTC, dias úteis, resolução de payload.
  - `resolve.py` — resolve nomes de projeto/tarefa/tag → IDs; `add_entries` com anti-duplicata.

## Convenções específicas (gotchas)

- **Config por-projeto** em `.clockify/` na pasta do projeto aberta no Cowork:
  - `credentials.json` (modo 0600) — api_key, ics_url, workspace_id/user_id em cache.
  - `prefs.json` — atividade padrão + learned (match → projeto/tarefa/tag).
  - Variável de ambiente `CLOCKIFY_DIR` tem precedência (CI/testes). `CLAUDE_PROJECT_DIR` é a base automática no Cowork.
  - `.clockify/` deve estar no `.gitignore` do projeto do usuário — nunca versionado.
- **Onboarding**: o usuário cola a API key uma vez no chat; a skill escreve `credentials.json`. Sem passos manuais.
- **Horários em UTC**: conversão de hora local (America/Sao_Paulo) em `pure.py`.
- **Anti-duplicata**: `entries` verifica o que já existe antes de `add`.
- **`add` é resiliente a falha parcial**: para no 1.º erro, reporta "gravou N de M", sai ≠ 0.
- **Sempre dry-run antes de gravar.**
- **Testes**: 100% stdlib, sem `uv`, sem dependências externas. `python3 -m pytest -q` direto em `clockify-cowork/scripts/`.

## Documentação relacionada

- `README.md` — setup e uso. `docs/superpowers/specs|plans/` — design histórico.
