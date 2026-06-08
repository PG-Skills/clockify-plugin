# Spec — clockify-cowork: arquitetura local (skill + scripts, sem servidor)

**Data:** 2026-06-08 · **Status:** aprovado no brainstorming, pronto para plano de implementação
**Supersede:** `2026-06-05-clockify-cowork-mcp-design.md` (MCP remoto + OAuth + VPS) — abandonado.
**Escopo desta entrega:** lançar horas no Cowork (dia **ou** período) com config **local** persistente.
**Fora de escopo:** agenda via ICS (fase 2), `/clockify-report` (fase 3).

---

## 1. Contexto e motivação (o pivô)

A arquitetura anterior (spec de 2026-06-05) moveu a lógica para um **MCP server remoto na VPS da PG**, com **OAuth** e a **chave cifrada no token/banco**, porque se acreditava que o Cowork era um sandbox efêmero remoto **sem acesso a arquivos locais persistentes** — logo a credencial não teria onde morar.

**Essa premissa estava errada.** Verificação empírica (2026-06-08, no app de desktop do Claude / Cowork, modo "Trabalhar em um projeto"):

- O Cowork opera sobre uma **pasta local do Mac** (ex.: `/Users/<user>/Devs`), escolhida como "projeto".
- O agente acessa essa pasta por dois caminhos sobre o **mesmo filesystem**: (a) file tools (Read/Write/Edit) com os paths reais do Mac; (b) um **terminal bash** num sandbox Linux (Ubuntu 22.04, ARM64) onde a pasta entra **montada**.
- O sandbox é efêmero (some entre sessões), **mas arquivos gravados dentro da pasta do projeto PERSISTEM** — é a pasta real do Mac.
- Plugins via marketplace funcionam; Python já vem no sandbox; **rodar Python/CLI no sandbox é coisa provada** (a CLI v1 já rodou lá no teste de 2026-06-05).

**Decisão:** abandonar VPS + OAuth + servidor remoto. A credencial e as preferências passam a viver em **arquivos na pasta do projeto** (persistem). O plugin deixa de ser uma casca para um connector remoto e passa a conter uma **skill** (cérebro) + um **CLI Python local** (braço). É uma ferramenta interna pequena; o norte é **simplicidade e onboarding fácil para leigos**.

---

## 2. Decisões travadas (brainstorming 2026-06-08)

| # | Decisão |
|---|---|
| D1 | **Abandonar** VPS, OAuth, criptografia e o MCP remoto. Decomissionar a stack `clockify-mcp` na VPS (sem tocar Traefik/outras stacks). |
| D2 | Continua **plugin no Cowork** (instalação por marketplace, 1 clique). O recheio muda para **skill + scripts**, **sem** declarar MCP server. |
| D3 | **Config local na pasta do projeto** (persiste): credenciais e preferências em arquivos sob `.clockify/`. |
| D4 | **Onboarding leigo:** na 1ª vez o Claude pede a chave **no chat**, valida, grava em `.clockify/`. Nunca mais pede. A pessoa **não edita arquivo**. |
| D5 | **CLI zero-dependência** (só stdlib Python): portar os chamados HTTP de `httpx`→`urllib`. Sem `pip install` no sandbox efêmero → nada pra quebrar. |
| D6 | **Reusar a lógica refinada** de `server/src/clockify_mcp/` (busca direcionada `resolve.py`, anti-duplicata por dia, payload/UTC de `pure.py`) — NÃO a CLI antiga (`plugins/clockify-plugin/`, que tinha o timeout do `meta`). |
| D7 | Comando **`/clockify-tracking`** (lançar dia **ou** período). **`/clockify`** vira um "está tudo certo?" (checa chave + conexão + o que está configurado). Slash em inglês; **conversa na língua do usuário** (i18n). |
| D8 | **Sempre dry-run + confirmação** antes de gravar; **anti-duplicata** por (dia local, tarefa). |
| D9 | **ICS (agenda do Outlook) → fase 2** (precisa de libs; mantém v1 zero-dep). `/clockify-report` → fase 3. |

**Trade-off aceito conscientemente (D1/D3):** a chave do Clockify de cada pessoa fica **em texto puro** na pasta dela e passa pelo **histórico da conversa** no onboarding. Era isso que o OAuth/cifragem comprava. Para ferramenta interna, cada um com a própria chave, a troca por "zero infra" é considerada válida. Mitigação: `.clockify/` **gitignored**; orientação de não commitar; chave é revogável no Clockify.

---

## 3. Arquitetura

```
   PESSOA no Cowork (app desktop, "Trabalhar em um projeto")
      │  /clockify-tracking → "lança minhas horas de hoje" (na língua dela)
      ▼
 ┌──────────────────────────────┐
 │  PLUGIN  clockify-cowork     │   (instalado via marketplace)
 │  ├─ skills/clockify-tracking │  ← o CÉREBRO: conversa, decide, verbaliza i18n
 │  ├─ commands/                │     /clockify-tracking, /clockify (status)
 │  └─ scripts/ (CLI zero-dep)  │  ← o BRAÇO: fala com a API do Clockify
 └──────────────────────────────┘
      │ Claude roda no terminal do sandbox:  python3 <cli> <subcomando> ...
      ▼
 ┌──────────────────────────────┐         ┌───────────────────────────────┐
 │  CLI zero-dependência (.py)  │ ──HTTP──►│  API REST do Clockify          │
 │  reusa pure/resolve (urllib) │  urllib  │  (api.clockify.me/api/v1)      │
 └──────────────────────────────┘         └───────────────────────────────┘
      │ lê/grava
      ▼
 ┌──────────────────────────────┐
 │  .clockify/ (na pasta do      │  ← PERSISTE (pasta real do Mac)
 │   projeto, gitignored)       │
 │  ├─ credentials.json         │     api_key, ics_url?, workspace_id (cache)
 │  └─ prefs.json               │     default + learned (título→projeto/tarefa)
 └──────────────────────────────┘
```

**Três peças, responsabilidade única cada:**

1. **Skill (`skills/clockify-tracking/SKILL.md`)** — o cérebro conversacional. Detecta idioma, conduz onboarding, escopo (dia/período), precedência de atividades (aprendida → padrão → perguntar), dry-run, confirmação, e chama o CLI. **Não tem lógica de HTTP.**
2. **CLI Python zero-dependência (`scripts/`)** — o braço de IO confiável. Subcomandos idioma-neutros que **retornam JSON** (dados, nunca frase pronta). Reusa a lógica pura/resolve do `server/`, com HTTP via `urllib`.
3. **Config local (`.clockify/`)** — estado persistente na pasta do projeto. Dois arquivos (credencial separada das preferências para isolar o sensível).

---

## 4. Config e onboarding

### Arquivos (sob `.clockify/` na pasta do projeto — `.clockify/` é gitignored)

- **`credentials.json`** (sensível): `{ "api_key": "...", "ics_url": null, "workspace_id": "<cache>" }`
- **`prefs.json`** (não-sensível): `{ "default": { "project": ..., "task": ..., "tag": ..., "billable": ... }, "learned": [ { "match": "...", "project": ..., "task": ..., "tag": ..., "billable": ... } ] }`

Caminho-base resolvido nesta ordem: `CLOCKIFY_DIR` (env) → `$CLAUDE_PROJECT_DIR/.clockify` → `./.clockify` (cwd). Decisão final do mecanismo de localização confirmada no plano com 1 teste no sandbox.

### Fluxo de onboarding (1ª vez, leigo)

0. **Pré-requisito — estar num projeto (pasta local).** A skill confirma (via `pwd`/`CLAUDE_PROJECT_DIR`) que há um projeto com pasta local; se não houver, instrui a pessoa a clicar em **"Trabalhar em um projeto"** e criar/escolher uma pasta (ex.: "Clockify") e **para** até existir — sem isso o `.clockify/` cairia no sandbox efêmero e não persistiria. Verificação no início de `/clockify` **e** de `/clockify-tracking`.
1. `/clockify-tracking` (ou `/clockify`) → skill roda `cli whoami`; sem credencial → erro estruturado `NO_KEY`.
2. Skill pede no chat, em linguagem leiga: *"Pra começar, cola aqui sua chave do Clockify — pego em https://app.clockify.me/user/settings."*
3. Pessoa cola → skill grava em `credentials.json` e roda `cli whoami` → valida chamando `GET /user`.
4. Sucesso → guarda `workspace_id` no cache, confirma com o nome da conta. **Nunca mais pede.**
5. Chave inválida → mensagem leiga e nova tentativa.

---

## 5. Comandos e skill

### `/clockify-tracking` (lançar dia ou período)

Fluxo conversacional (skill), **na língua do usuário**:

1. **Escopo:** "Lançar **hoje** (ou um dia) ou um **período**?"
2. **(Período)** intervalo → `cli business-days --start --end` → mostra dias úteis → poda exceções.
3. **Anti-duplicata:** `cli entries --date|--start --end` → avisa dias já lançados (omite-os).
4. **Reconhecer atividades** por dia, precedência **(1) aprendida → (2) padrão → (3) perguntar** (linguagem leiga: "qual cliente/projeto?"). Em v1, sem ICS, a pessoa dita; com ICS (fase 2) o Claude sugere pela agenda.
5. **Resolução:** `cli resolve --name <tarefa> --project <projeto> [--tag]` → JSON `OK | AMBIGUO | NAO_ENCONTRADO` (+ candidatos). Skill desambigua conversando. (Tarefa exige projeto — endpoint do Clockify exige `projectId`.)
6. **Conferência:** tabela limpa (sem jargão/IDs) → confirma.
7. **Gravar:** `cli add --json - --dry-run` primeiro (mostra o que faria), depois `cli add --json -` real. Resiliente a falha parcial (para no 1º erro, reporta "gravou N de M").
8. **Aprender** (opcional, com consentimento): `cli prefs learn ...`.

### `/clockify` (status / "está tudo certo?")

Roda `cli whoami` + lista o que está configurado (conta conectada, atividade padrão, nº de atividades aprendidas). Se faltar chave, dispara o onboarding. Substitui o antigo "confirma conexão" do connector remoto.

---

## 6. O CLI zero-dependência

Pacote `scripts/clockify_cli/` (ou módulo único), **só stdlib** (`urllib.request`, `json`, `argparse`, `datetime`, `zoneinfo`). Reuso:

| Origem (`server/src/clockify_mcp/`) | Vai pro CLI |
|---|---|
| `pure.py` (totais, `to_utc_iso`, `range_window_utc`) | **copiado quase intacto** (já é stdlib). |
| `resolve.py` (`resolve_activity`, `add_entries`, anti-duplicata por dia) | **portado de async→sync** (mesma lógica, sem `await`). |
| `clockify.py` (get_user/search_*/entries/create_entry) | **portado de `httpx`→`urllib`** (mesmos endpoints, `X-Api-Key`, paginação, busca `strict-name-search`). |
| `ics.py` | **fase 2** (precisa de `icalendar`/`recurring-ical-events`). |

**Some:** `auth.py`, `crypto.py`, `app.py`, `serve.py`, `tools.py` (MCP), `settings.py` (vira leitura de `.clockify/`), `prefs.py` (SQLite → `prefs.json` simples).

### Subcomandos (todos imprimem **JSON** em stdout; idioma-neutro)

| Subcomando | Função |
|---|---|
| `whoami` | Valida a chave; `{name,email,workspace_id}` ou `{error:"NO_KEY"\|"INVALID_KEY"}`. |
| `business-days --start --end` | Dias úteis seg–sex (pure). |
| `entries --date \| --start --end` | Lançamentos existentes na janela (anti-duplicata). |
| `resolve --name --project [--tag]` | Busca direcionada nome→IDs; `OK\|AMBIGUO\|NAO_ENCONTRADO` + candidatos. |
| `add --json - [--dry-run]` | Lê items (JSON via stdin), resolve+grava com anti-duplicata; `--dry-run` só simula. `{gravados,total,pulados_duplicata,falhou_em,motivo}`. |
| `prefs get \| set-default \| learn` | Lê/grava `prefs.json`. |

---

## 7. Execução no sandbox e dependências

- **Zero-dependência (D5)** → **nenhum `pip install`** no sandbox efêmero. O CLI é só `.py` stdlib; roda imediatamente. Elimina a maior fonte de fragilidade/lentidão e de "quebrou de novo".
- **Onde o CLI roda:** preferência `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/...` se o sandbox alcançar os arquivos do plugin; fallback: a skill copia os `.py` (pequenos, stdlib) para `.clockify/bin/` na 1ª execução (persiste). **Mecanismo final confirmado por 1 teste de 2 min no plano** (Passo 0).
- **Horários em UTC:** conversão de hora local (`America/Sao_Paulo`) preservada de `pure.py`.

---

## 8. Segurança

- Sem servidor, sem porta aberta, sem TLS pra manter, sem segredo de servidor.
- Chave do Clockify: **texto puro** em `.clockify/credentials.json` na máquina da pessoa (trade-off aceito, §2). `.clockify/` **gitignored**; a chave é revogável a qualquer momento no Clockify.
- Onboarding expõe a chave no transcript da conversa (Anthropic) — aceitável para ferramenta interna, documentado para o usuário.
- Sem PII além do necessário; `prefs.json` não tem segredo.

---

## 9. O que sai (limpeza/migração)

- **Remover/arquivar** `server/` inteiro (FastMCP, OAuth, crypto, tools MCP, prefs SQLite).
- **Remover** o connector remoto do plugin: `clockify-cowork/.mcp.json` + `mcpServers` em `plugin.json`.
- **Remover/arquivar** a CLI antiga `plugins/clockify-plugin/` (lógica inferior; a nova reusa o `server/`).
- **Decomissionar** a stack `clockify-mcp` na VPS — parar/remover o container e labels Traefik **sem tocar** `/docker/traefik/` nem as outras stacks. (Passo separado, não bloqueia o plugin.)
- Atualizar `README.md`, `CLAUDE.md`, `MAINTAINER.md` para a arquitetura local.

---

## 10. Riscos

| Risco | Mitigação |
|---|---|
| `${CLAUDE_PLUGIN_ROOT}`/scripts do plugin **não alcançáveis** no terminal do sandbox | **Passo 0 (teste de 2 min)** confirma; fallback = copiar `.py` para `.clockify/bin/`. Zero-dep garante que, alcançado o arquivo, roda. |
| Pessoa **commita** `.clockify/` com a chave | `.gitignore` cobre `.clockify/`; skill avisa; chave revogável. |
| Pasta do projeto trocada → config "some" | É por-pasta por design; `/clockify` mostra o estado; onboarding re-pede (rápido). Documentar "use a mesma pasta". |
| Workspace com ~1000 tarefas → timeout (problema do `meta` antigo) | Já mitigado: **busca direcionada** (`strict-name-search`), nunca lista o workspace inteiro. |
| Port `httpx`→`urllib` introduzir bug sutil (paginação, headers, erros) | Testes portados de `server/tests` (com `urllib` mockado); paridade de comportamento como critério. |

---

## 11. Testing strategy (resumo — detalhar no plano via `testing-strategy`)

- **Lógica pura** (`pure`): testes diretos (totais, UTC, janela).
- **CLI/HTTP** (`clockify`, `resolve`, `add`): portar os testes de `server/tests` substituindo o mock de `httpx` por mock de `urllib` (ou `http.server` local). Critério: **paridade** com o comportamento atual (busca direcionada, anti-duplicata por dia, falha parcial).
- **Config/onboarding:** ler/gravar `.clockify/`, casos `NO_KEY`/`INVALID_KEY`.
- **Smoke manual no Cowork:** Passo 0 (CLI roda no sandbox) + 1 lançamento dry-run→real numa conta real.

---

## 12. Fora de escopo (esta entrega)

- **Agenda via ICS** (sugerir lançamentos pela agenda do Outlook) → **fase 2** (reintroduz `ics.py` + libs; avaliar zero-dep parser ou aceitar a dep só nesse fluxo).
- **`/clockify-report`** → **fase 3**.
- **Multi-pessoa centralizado** (voltar a um backend) → descartado para esta linha; se um dia exigir gestão central, é outra arquitetura.
