# CLAUDE.md

Wrapper fino para o Claude Code neste repositório. Detalhes de uso ficam no `README.md`.

## Comandos principais

Rodar dentro de `clockify-plugin/scripts/`:

```bash
python3 -m pytest -q        # testes (stdlib only, sem uv)
```

## Arquitetura

Plugin `clockify-plugin/` = **skill conversacional** + **CLI Python zero-dependência** (stdlib).
Roda no Claude desktop app ("Cowork") sobre uma pasta de projeto local.
**Sem servidor, sem OAuth, sem VPS.**

- `clockify-plugin/skills/clockify-tracking/SKILL.md` — skill principal, orquestra a conversa.
- `clockify-plugin/commands/clockify-tracking.md` — comando `/clockify-tracking` (lançar um dia ou período).
- `clockify-plugin/commands/clockify.md` — comando `/clockify`, **único dono do setup**: pasta → chave → **ICS do Outlook (obrigatório)** → manual rápido.
- `clockify-plugin/skills/clockify-tracking/references/manual-rapido.md` — roteiro do manual de boas-vindas (lido pelo `/clockify` ao concluir o setup; apresentado na língua da pessoa).
- `clockify-plugin/skills/clockify-report/SKILL.md` + `commands/clockify-report.md` — `/clockify-report` (relatório diário/mensal, read-only).
- `clockify-plugin/scripts/clockify_cli/` — CLI zero-dep (Python stdlib):
  - `cli.py` — subcomandos `whoami`, `setup-status` (guard local, sem rede: `{configured,has_key,has_ics,dir}`), `entries` (`--date` | `--start/--end`), `business-days`, `resolve`, `add` (`--dry-run`), `agenda` (`--date`, lê ICS), `report` (`--month` diário | `--start/--end` mensal ≤12), `prefs` (`get`/`set-default`/`learn`/`forget`/`reset`).
  - `clockify.py` — client HTTP para a API Clockify (`https://api.clockify.me/api/v1`). `entries(..., hydrated=True)` traz `project`/`task`/`tags` expandidos (nome do projeto no report).
  - `http_json.py` — HTTP mínimo via `urllib` (sem requests).
  - `ics.py` — leitor de agenda Outlook (ICS) zero-dep: fetch anti-SSRF + parser + recorrência (DAILY/WEEKLY/MONTHLY).
  - `config.py` — lê/escreve `.clockify/credentials.json` no projeto (api_key + workspace_id/user_id em cache + ics_url).
  - `prefs.py` — preferências por projeto em `.clockify/prefs.json` (default projeto/tarefa/tag/billable + learned).
  - `pure.py` — lógica pura: janelas UTC (dia/intervalo/mês), dias úteis, agregação de horas por dia/mês + por projeto, resumo (média/dia-mês mais cheio), lacunas de dias úteis (report), payload/UTC.
  - `resolve.py` — resolve nomes de projeto/tarefa/tag → IDs; `add_entries` com anti-duplicata por (tarefa, início).

## Convenções específicas (gotchas)

- **Config por-projeto** em `.clockify/` na pasta do projeto aberta no Cowork:
  - `credentials.json` (modo 0600) — api_key, ics_url, workspace_id/user_id em cache.
  - `prefs.json` — atividade padrão + learned (match → projeto/tarefa/tag).
  - Variável de ambiente `CLOCKIFY_DIR` tem precedência (CI/testes). `CLAUDE_PROJECT_DIR` é a base automática no Cowork.
  - `.clockify/` deve estar no `.gitignore` do projeto do usuário — nunca versionado.
- **Onboarding (só `/clockify`)**: o usuário cola a API key e conecta a **agenda do Outlook (obrigatória, link `.ics` via "Publicar calendário")**; o `/clockify` escreve `credentials.json`. `/clockify-tracking` e `/clockify-report` **não** fazem setup.
- **Guard de pasta configurada**: `tracking` e `report` rodam `setup-status` como 1ª ação. `has_key:false` → mande rodar `/clockify` ou abrir a pasta certa no Cowork; `has_ics:false` → setup incompleto, mande concluir no `/clockify`. "Configurado" = chave **+** ICS.
- **Horários em UTC**: conversão de hora local (America/Sao_Paulo) em `pure.py`.
- **Anti-duplicata**: chave `(tarefa, início)` — vários blocos da mesma tarefa no dia entram; só re-run idêntico (mesma tarefa e mesmo início) é pulado.
- **`add` é resiliente a falha parcial**: para no 1.º erro, reporta "gravou N de M", sai ≠ 0.
- **Sempre dry-run antes de gravar.**
- **Testes**: 100% stdlib, sem `uv`, sem dependências externas. `python3 -m pytest -q` direto em `clockify-plugin/scripts/`.

## Documentação relacionada

- `README.md` — setup e uso. `docs/superpowers/specs|plans/` — design histórico.
