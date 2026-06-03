# Clockify Plugin Compartilhável (multiusuário) — Design

**Data:** 2026-06-03
**Autor:** vbjuliani (PG Consulting)
**Status:** Aprovado (design) — pendente plano de implementação
**Relacionado:** generaliza [[2026-05-21-lancador-horas-clockify-design]] e [[2026-05-21-lancador-batch-clockify-design]] para uso por toda a equipe.

## Problema

Várias pessoas da empresa querem usar o lançador de horas, mas cada uma tem **suas
próprias** credenciais Clockify, workspace, calendário Outlook e projetos/tarefas/etiquetas.
Hoje o que é específico do autor está espalhado em três lugares: `.env` (creds — já
por-pessoa e gitignored), `defaults.json` (commitado, com `Time IA` / `Célula de Inovação`)
e o texto dos slash commands `/horas` e `/lancar` (defaults e exemplos de cliente escritos
no prompt). Overrides de cliente vivem na auto-memória pessoal do Claude.

Objetivo: transformar o projeto num **pacote compartilhável** que (a) não contém nenhum
dado pessoal do autor, (b) instala da forma mais simples possível, (c) tem onboarding
guiado com UX forte, e (d) deixa cada pessoa plugar a própria configuração.

## Decisões tomadas (brainstorming)

| Tema | Decisão |
|---|---|
| Público | **Todos usam Claude Code.** Distribuição 100% nativa do CC. |
| Plataformas | **macOS, Windows e Linux** (todos via Claude Code). Bootstrap da CLI em **Python** (cross-platform), não bash. Paths e permissões tratados por SO. |
| Dependência única | **`uv`** (binário standalone). **Não requer Python pré-instalado** — o `uv` baixa um Python gerenciado ao instalar/rodar a CLI (`requires-python` guia a versão). Se faltar `uv`, o hook avisa (não instala sozinho) e o `/clockify-setup` oferece instalá-lo com consentimento (instalador oficial, por SO), pedindo para reabrir a sessão. |
| Distribuição | **Plugin via marketplace privado** (repo git). `/plugin marketplace add` + `/plugin install`. Atualização via `/plugin update`. |
| Onboarding | **Setup guiado por skill** (`/clockify-setup`) — conversa, auto-descobre, grava config. |
| Dono da config | **Caminho A — CLI dona do I/O.** Novo subcomando `config`; a skill só orquestra. Preserva a separação cérebro/IO. |
| Overrides de cliente | **Seção estruturada no config**, mas **vazia no pacote**. Cada pessoa declara os seus (opcional). Overrides do autor permanecem só na config local dele. |
| Formato/local da config | **JSON único**, zero-dependência. Local por SO: `$XDG_CONFIG_HOME` (prioridade, em qualquer SO) → `%APPDATA%/clockify-horas/config.json` no Windows → `~/.config/clockify-horas/config.json` no resto. Permissão `600` só em POSIX. |
| `defaults.json` | **Removido do repo.** Não vira fallback — config por-usuário é a única fonte. |
| Instalação da CLI | **SessionStart hook** (`scripts/ensure_cli.py` via `uv run --script`) instala/atualiza a CLI com guard de versão — cross-platform, sem bash. `${CLAUDE_PLUGIN_ROOT}` só expande em hook, por isso não fica no corpo da skill. `/clockify-setup` vira puro wizard de config e só orienta a instalar `uv` (por SO) se faltar. |

## Princípio guia

O **comportamento do motor não muda**. Muda (1) **de onde** ele lê a config — sai o
acoplamento com `defaults.json`/`.env` no diretório do projeto, entra um config por-usuário;
e (2) **como** o pacote é distribuído e configurado. A separação cérebro/IO fica mais forte:
a skill conversa, a CLI faz I/O determinístico e testável.

UX é requisito de primeira classe, não enfeite. Cinco regras:
1. **Um comando de entrada faz tudo** (`/clockify-setup`) — nada de "passo 0: instale Python".
2. **Perguntar o mínimo** — auto-descobrir sempre que possível.
3. **Escolher por número, não digitar nome** — elimina erro de digitação de tarefa/etiqueta.
4. **Falhar com mensagem clara** — `config doctor` diz exatamente o que está errado.
5. **Provar antes de declarar pronto** — toda config termina com verificação real contra a API.

## Arquitetura

```
clockify-horas/                      (repo = plugin + marketplace privado)
├── .claude-plugin/
│   ├── plugin.json                  # manifesto do plugin (nome, versão, componentes)
│   └── marketplace.json             # marketplace de 1 item (lista o próprio plugin)
├── commands/
│   ├── horas.md                     # /horas — generalizado (sem dado pessoal)
│   └── lancar.md                    # /lancar — generalizado
├── skills/
│   └── clockify-setup/SKILL.md      # /clockify-setup — onboarding guiado
├── src/clockify_horas/              # CLI (igual + subcomando `config`)
├── tests/
├── README.md                        # reescrito p/ time
└── MAINTAINER.md                    # como o mantenedor corta release
```

Nota de migração de layout: hoje os slash commands vivem em `.claude/commands/`. No formato
de plugin do Claude Code eles passam a `commands/` (raiz do plugin) e a skill em `skills/`.
A estrutura exata de `plugin.json`/`marketplace.json` será confirmada contra a doc oficial
do Claude Code no início da implementação (Fase 4), via `claude-code-guide` se necessário.

### Fluxo de config

```
/clockify-setup (1ª vez)            /horas, /lancar (uso diário)
   │                                    │
   ▼                                    ▼
Claude (orquestra a conversa)       Claude (orquestra)
   • confere CLI (instalada via hook)  • clockify-horas config show → defaults + overrides
   •   e oferece instalar uv se faltar
   • config set (key/workspace/ics)    • aplica defaults; casa overrides por palavra-chave
   • meta → lista tasks/tags           • (resto do fluxo atual: agenda/business-days,
   • config set (defaults)             •  anti-duplicata, dry-run, add) inalterado
   • config add-override (opcional)    │ chama
   • config doctor → prova             ▼
   │ chama                          clockify-horas (CLI)
   ▼
clockify-horas config (NOVO)        config show / path (lido pelos commands)
```

## Componentes

### Config por-usuário (`~/.config/clockify-horas/config.json`)

```json
{
  "clockify":  { "api_key": "...", "workspace_id": "..." },
  "outlook":   { "ics_url": "..." },
  "defaults":  { "task_name": "...", "tag_name": "...",
                 "billable": false, "daily_target_hours": 8.0 },
  "overrides": [
    { "match": "<palavra-chave>", "task_name": "...",
      "tag_name": "...", "billable": true }
  ]
}
```

- Localização (por SO): `$XDG_CONFIG_HOME/clockify-horas/config.json` se definido →
  `%APPDATA%/clockify-horas/config.json` no Windows → `~/.config/clockify-horas/config.json`
  no resto. `$XDG_CONFIG_HOME` tem prioridade em qualquer SO (usado para isolar testes).
- Criado/atualizado **somente** pelo subcomando `config` (I/O determinístico). Escrita com
  `chmod 600` apenas em POSIX (no-op no Windows).
- `overrides` começa `[]` no pacote. Os do autor ficam apenas na config local dele.

### `config.py` (estendido)

- Passa a ler de `~/.config/clockify-horas/config.json`.
- **Precedência:** variável de ambiente > arquivo de config. Preserva os testes atuais
  (que setam env vars) e um eventual uso em CI. `OUTLOOK_ICS_URL`, `CLOCKIFY_API_KEY`,
  `CLOCKIFY_WORKSPACE_ID` continuam sobrepondo o arquivo quando presentes.
- Novos loaders: `load_config`, `load_defaults`, `load_overrides`. Erro claro e acionável
  quando o arquivo não existe ("rode `/clockify-setup`") ou falta campo obrigatório.
- `defaults.json` deixa de ser lido (arquivo removido do repo).

### `config` (novo subcomando — I/O determinístico)

| Comando | Faz |
|---|---|
| `config path` | imprime o caminho do arquivo de config |
| `config show` | imprime a config atual em JSON com a **api_key redigida** — consumido pelos slash commands |
| `config set [--api-key/--workspace-id/--ics-url/--task/--tag/--billable/--no-billable/--daily-target]` | cria/atualiza campos; idempotente; cria o diretório e o arquivo se faltarem |
| `config add-override --match M --task T --tag G [--billable/--no-billable]` | adiciona uma regra à lista `overrides` |
| `config doctor` | valida campos obrigatórios; chama `meta` para confirmar key+workspace; testa alcance do ICS; sai ≠0 com diagnóstico por item em falha |

`config show` é a interface que `/horas` e `/lancar` usam para obter defaults e overrides
sem hardcode no prompt.

### `/clockify-setup` (nova skill — onboarding guiado)

Conversa em português, um passo de cada vez, sempre delegando I/O à CLI:

1. **Dependências** — confere `clockify-horas` no PATH (instalado pelo **SessionStart hook**,
   não pela skill — `${CLAUDE_PLUGIN_ROOT}` só expande em hook). Se faltar, a causa quase
   sempre é `uv` ausente: a skill **oferece instalar o `uv`** (instalador oficial por SO, com
   consentimento) e pede para reabrir a sessão, quando o hook instala a CLI. Não requer Python
   pré-instalado.
2. **Local** — `config path`; se já existe config, oferece reconfigurar.
3. **API key** — pede a key com o clique-a-clique do Clockify → `config set --api-key`.
4. **Workspace** — `meta` lista workspaces; **se houver só 1, escolhe sozinho**; senão,
   lista numerada → `config set --workspace-id`.
5. **ICS** — pede o link com o passo-a-passo de publicar no Outlook → `config set --ics-url`.
6. **Defaults** — `meta` lista tasks/tags reais como **lista numerada**; pessoa escolhe
   task/tag/faturável; meta diária 8h e não-faturável **pré-preenchidos** → `config set`.
7. **Overrides (opcional, pulável)** — "quer pré-declarar algum cliente? (pode pular)".
   Default: pular. Se sim, loop `config add-override`.
8. **Prova** — `config doctor` (resumo verde) e oferece um `/horas` em **dry-run** de teste,
   sem gravar nada.

Re-rodar `/clockify-setup` é idempotente (reconfigura/edita).

### `/horas` e `/lancar` (generalizados)

- Removem todo texto pessoal (`Time IA`, `Célula de Inovação`, `tag AMS`, exemplos de cliente).
- Passo inicial roda `clockify-horas config show` e **aplica os defaults e overrides da pessoa**.
- Onde hoje citam um cliente específico, viram genéricos: "se o item casar com um override
  configurado (`match`), aplique-o; senão, pergunte e valide contra `meta`".
- Anti-duplicata, dry-run, confirmação e gravação resiliente: **inalterados**.
- Se `config show` falhar (sem config), instruem rodar `/clockify-setup` antes.

## Error handling

- **Sem config** → mensagem clara mandando rodar `/clockify-setup`; nenhum command quebra com stack trace.
- **Key/workspace inválidos** → `config doctor` aponta qual falhou (HTTP 401 vs workspace inexistente).
- **ICS fora do ar** → `doctor` sinaliza, mas não bloqueia setup (lançamento batch `/lancar` não usa ICS).
- **Tarefa/tag não resolvida** no uso → `build_payload` já levanta erro com o nome ofensor (inalterado).
- **`uv` ausente e instalação falha** → setup para com instrução manual de fallback (1 comando).
- **Precedência env vs arquivo** → documentada; testes cobrem ambos os caminhos.

## Testes

- `config.py`: lê do dir do usuário (`tmp_path` + monkeypatch de `$XDG_CONFIG_HOME`/`$HOME`);
  precedência env > arquivo; erro claro quando arquivo ausente/campo faltando.
- `config` subcomando: `set` cria e atualiza idempotente; `show` redige a key; `add-override`
  acrescenta; `path` correto; `doctor` verde e vermelho (via `respx` mockando `meta`).
- Permissão `600` no arquivo escrito.
- Slash commands não têm teste automatizado (são prompt) — validados no dogfood (Fase 5).
- Suíte atual segue verde (env-var override preserva `test_config.py`).

## Plano de fases (visão)

1. **Fundação** — config relocation + subcomando `config` + testes.
2. **Generalização** — `/horas` e `/lancar` sem dado pessoal; remover `defaults.json`.
3. **Onboarding** — skill `/clockify-setup`.
4. **Empacotamento** — `plugin.json` + `marketplace.json` + `MAINTAINER.md` + README de time.
5. **Dogfood** — autor reinstala do zero como plugin e valida o onboarding ponta a ponta.

## Fora de escopo (YAGNI v1)

- Servidor/DB central — cada pessoa é 100% local.
- Multi-workspace por pessoa (escolhe 1 no setup).
- OAuth do Outlook / Microsoft Graph — mantém ICS publicado.
- Trava anti-duplicata no `add` (igual hoje — anti-duplicata é `entries` + omissão manual).
- UI web.
- Migração automática da config antiga do autor (ele roda `/clockify-setup` como todo mundo;
  seus overrides ele recadastra na config local).
