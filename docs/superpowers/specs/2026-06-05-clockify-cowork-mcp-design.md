# Spec — clockify-plugin v2.0: Cowork + MCP remoto (Fundação de lançamento)

**Data:** 2026-06-05 · **Status:** aprovado no brainstorming, pronto para plano de implementação
**Escopo desta entrega:** Fundação de lançamento (onboarding + lançamento de horas no Cowork).
**Fora de escopo:** `/clockify-report` (fase 2) e o Claude Code (abandonado — ver Contexto).

---

## 1. Contexto e motivação

O plugin `clockify-plugin` v1.0 (CLI Python local + slash commands + hook de auto-instalação via `uv`) foi feito para o **Claude Code (terminal)**. O requisito mudou para **mandatório no Claude Cowork**, e os testes reais no Cowork (2026-06-05) expuseram dois tetos da arquitetura CLI-local:

1. **Efemeridade:** o Cowork roda num sandbox Linux temporário que **zera entre sessões** — a config (chave do Clockify) some, exigindo refazer o `/clockify-setup` toda sessão. Inaceitável para usuários leigos.
2. **Performance:** o comando `meta` (lista o workspace inteiro — ~40 projetos / ~1000 tarefas, paginado) **estourou o timeout** do sandbox.

**Decisão:** mover a lógica de uma CLI-na-máquina para um **MCP server remoto hospedado na VPS da PG**, consumido pelo Cowork como um **connector**. Foco **100% Cowork**; o Claude Code é **abandonado** (remove CLI/hook/lockstep/`uv` — menos superfície, menos erro). A lógica de IO existente é reaproveitada.

---

## 2. Decisões travadas (brainstorming 2026-06-05)

| # | Decisão |
|---|---|
| D1 | Foco **100% Cowork**; abandonar o Claude Code. |
| D2 | **MCP server remoto** hospedado na **VPS da PG** (HTTPS público). |
| D3 | **Credencial stateless:** o servidor **não armazena** a chave do Clockify. |
| D4 | Auth via **OAuth** (única opção do connector do Cowork): a pessoa cola a chave numa **página nossa**; o servidor **embute a chave criptografada no token**. |
| D5 | **Preferências** (atividade padrão + atividades aprendidas) ficam num **store leve no servidor**, por usuário, identificadas pelo ID do Clockify. **Nunca a chave.** |
| D6 | Comandos: **`/clockify-tracking`** (lançar dia **ou** período, unifica /lancar+/lancar-dias). `/clockify-report` é fase 2. Slash em inglês; **conversa na língua do usuário** (i18n). |
| D7 | **Resolução leve:** busca direcionada por nome/projeto + cache (mata o timeout do `meta`). |
| D8 | **Branding PG** na página de login (logo, azul corporativo, accent laranja — de `pgconsulting-group.com`). |
| D9 | Endpoint = **subdomínio do hostname Hostinger** (ex.: `clockify.srv1625247.hstgr.cloud`), sem domínio próprio. |
| D10 | Stack = **Python** (FastMCP), reaproveitando o código atual. |
| D11 | Template de infra/auth = **PGBrain** (MCP remoto já no ar na mesma VPS). |

---

## 3. Arquitetura

```
   PESSOA no Cowork
      │  /clockify-tracking → "lança minhas horas de hoje" (na língua dela)
      ▼
 ┌────────────────────┐    MCP (HTTPS + Bearer token)   ┌──────────────────────────────┐
 │  PLUGIN (casca)    │ ───────────────────────────────►│  MCP SERVER (Python/FastMCP) │
 │  commands + skills │                                 │  na VPS da PG, atrás do       │
 │  (.mcp.json →      │                                 │  Traefik (TLS LE)             │
 │   connector)       │                                 │  ┌─────────────────────────┐ │
 └────────────────────┘                                 │  │ Ferramentas MCP          │ │
                                                         │  │ (lançar, listar, resolver)│ │
   1ª vez (OAuth):                                       │  └─────────────────────────┘ │
   PESSOA ─navegador─► PÁGINA DE LOGIN (branding PG) ──► │  fala com:                    │
            cola a chave do Clockify (+ ICS opcional)    │   ├─► API REST do Clockify    │
                                                         │   └─► ICS do Outlook (URL)    │
                                                         │  store leve: preferências     │
                                                         │  (default + learned por user) │
                                                         └──────────────────────────────┘
```

**Três peças:**

1. **Plugin (casca)** — no Cowork. Só `commands/` + `skills/` + o connector MCP declarado (`.mcp.json` apontando para o subdomínio da VPS). **Sem código pesado.** É a conversa.
2. **MCP server (Python/FastMCP)** — na VPS da PG. O coração: expõe ferramentas, fala com Clockify e ICS, resolve tarefas, guarda preferências. Reaproveita `clockify_api.py`, `ics.py`, `entries.py`, `bizdays.py`, `learned.py` (núcleo de IO já testado).
3. **Página de login (OAuth)** — parte do servidor. Tela web com a identidade PG onde a pessoa cola a chave do Clockify. Aparece **uma vez**.

---

## 4. Onboarding e autenticação (OAuth stateless)

### Fluxo

1. Pessoa instala o plugin no Cowork → o connector MCP é adicionado.
2. Na 1ª chamada, o Cowork detecta que o servidor exige OAuth (descoberta via `/.well-known/oauth-authorization-server` + **Dynamic Client Registration**) e **abre o navegador do sistema** na nossa página `/authorize`.
3. A página (branding PG, multilíngue) pede a **chave do Clockify** (com "onde pegar") e, opcionalmente, o **link ICS** do Outlook.
4. O servidor **valida a chave** chamando `GET /user` no Clockify → obtém `user_id` e `email`.
5. O servidor emite um **access token (JWT)** contendo:
   - `clockify_key`: **criptografada** (AES-GCM com chave simétrica do servidor, off-repo).
   - `ics_url`: criptografada (se fornecida).
   - `clockify_user_id`: em claro (identificador não-sensível das preferências).
6. O Cowork guarda o token (persistente — confirmado: sobrevive a restart) e o envia como `Authorization: Bearer` em cada chamada MCP.
7. A cada chamada, o servidor **descriptografa** o token → extrai a chave → usa → **descarta**. Nunca persiste a chave.

### Propriedades

- **Stateless para a credencial** (D3): a chave vive no token do Cowork, não num banco nem no sandbox efêmero. Resolve a efemeridade.
- **Sem Microsoft Entra, sem login corporativo:** o servidor **é** o provedor OAuth; o "consentimento" é colar a chave do Clockify.
- **Espelhar o PGBrain:** ele já implementa "OAuth Resource Server (RFC 9728)" para Cowork — reusar a abordagem/scaffolding.

---

## 5. Preferências (store leve no servidor)

- O servidor mantém um **store leve** (ex.: SQLite no volume do container, ou Postgres se já houver) com **apenas dados não-sensíveis**, indexados por `clockify_user_id`:
  - **Atividade padrão** (`default`): projeto/tarefa/tag/faturável/meta-diária opcionais.
  - **Atividades aprendidas** (`learned`): lista de `match → (project, task, tag, billable)`.
- **Nunca** armazena a chave do Clockify nem o ICS.
- Reaproveita a lógica de `learned.py` (upsert por `match`, leitura), adaptada de arquivo-local para store-por-usuário.

---

## 6. Comando `/clockify-tracking`

Unifica o antigo `/lancar` + `/lancar-dias`. Fluxo conversacional (skill), **na língua do usuário**:

1. **Escopo:** "Quer lançar **hoje** (ou um dia) ou um **período**?"
2. **(Período)** pergunta o intervalo → ferramenta `business_days` → apresenta dias úteis → poda exceções.
3. **Anti-duplicata:** ferramenta `entries` por dia/intervalo → avisa dias já lançados.
4. **Reconhecer atividades** (por dia), precedência: **(1) aprendida → (2) padrão → (3) perguntar**. Lê a agenda via ferramenta `agenda` (se ICS configurado) ou a pessoa dita.
5. **Resolução leve** (D7): para validar/resolver uma tarefa, o servidor faz **busca direcionada** (filtro por nome/projeto na API do Clockify) + **cache** de projetos/tarefas por workspace (TTL). **Nunca** baixa o workspace inteiro.
6. **Conferência:** mostra tabela limpa (sem jargão) → confirma.
7. **Gravar:** ferramenta `add_entries` (resolve nomes→IDs com a busca direcionada; resiliente a falha parcial).
8. **Aprender** (opcional, com consentimento): ferramenta `learn_activity`.

### Ferramentas MCP expostas (rascunho)

| Ferramenta | Função |
|---|---|
| `list_projects` | Lista projetos (para a PoC e ambiguidade) — **paginado com cache**, não no caminho quente. |
| `resolve_activity(name, project?)` | Busca direcionada: nome→(projeto,tarefa,tag,ids). |
| `agenda(date)` | Lê a agenda do ICS de um dia (expande recorrências, ignora cancelados). |
| `entries(date \| start,end)` | Lança­mentos existentes (anti-duplicata). |
| `business_days(start,end)` | Dias úteis seg–sex. |
| `add_entries(items[])` | Cria os lançamentos (resolve nomes→IDs; resiliente a falha parcial). |
| `get_prefs` / `set_default` / `learn_activity` | Lê/grava preferências do usuário (store leve). |

> Idioma: as ferramentas **retornam dados** (idioma-neutro); o Claude verbaliza na língua do usuário. As mensagens da página de login são multilíngues (detectadas por `Accept-Language`).

---

## 7. Branding (página de login)

- Identidade de `pgconsulting-group.com`: **logo PG** (badge azul + "PG Consulting"), **azul corporativo** (gradiente navy→royal) como dominante, **accent laranja-avermelhado** (CTA), base branca, sans-serif, cantos arredondados, tom corporativo/confiável.
- Hex exatos a extrair do CSS do site na implementação. Logo: `https://pgconsulting-group.com/wp-content/uploads/2024/02/logo-pg-consulting-horizontal-branco-1024x253.png`.
- Página **responsiva**, mínima: logo, título ("Conectar o Clockify"), campo da chave (+ "onde pegar"), campo ICS opcional, botão "Autorizar". Multilíngue (PT/EN/ES).

---

## 8. Infra e deploy (espelha o PGBrain)

- **Endpoint:** `clockify.srv1625247.hstgr.cloud` (D9) — subdomínio do hostname Hostinger, sem domínio próprio.
- **Deploy:** compose project sibling em `/docker/clockify-mcp/`, atrás do **Traefik externo compartilhado**, rede própria (`clockify-net`), **sem `ports:` publicados** (Traefik termina TLS), labels:
  - `traefik.http.routers.clockify.rule=Host(\`clockify.srv1625247.hstgr.cloud\`)`
  - `entrypoints=websecure` · `tls.certresolver=letsencrypt`
- **Stack:** Python (FastMCP) num container; `mem_limit` declarado (~512 MB–1 GB; a VPS tem ~4.5 GB livre).
- **Secrets** (chave de criptografia do token, etc.) via env var do container, off-repo.
- **Source-of-truth:** este repo (`PG-Skills/clockify-plugin`) ganha o servidor; deploy por SCP/git na VPS (alinhar com o padrão OpenClawPG/PGBrain).

---

## 9. ▶ Passo 1 — PoC do OAuth (derruba o risco crítico primeiro)

Antes de construir o resto, validar o **caminho crítico** (OAuth no Cowork tem bugs de plataforma conhecidos):

**Escopo mínimo:**
- Servidor FastMCP no subdomínio Hostinger, com TLS LE válido.
- OAuth leve (well-known + DCR + PKCE + `/authorize` + `/token`) com a chave embutida no token.
- Página de login mínima (sem branding final ainda).
- **1 ferramenta leve:** `whoami` (chama `GET /user` no Clockify → nome/email) — prova que a chave do token funciona, sem o peso do `meta`.

**Critério de sucesso:**
1. Adicionar o connector no Cowork → o navegador abre a página → colar a chave → autorizar.
2. A ferramenta `whoami` responde dentro do Cowork com o nome da conta (chave válida, ponta a ponta).
3. **Fechar e reabrir** o Cowork → a sessão continua autenticada (token persiste), sem recolar a chave.

Se a PoC passar, seguimos com o restante da Fundação. Se tropeçar num bug de OAuth do Cowork, reavaliamos com custo mínimo.

---

## 10. Segurança

- **Chave do Clockify nunca em repouso** no servidor (só criptografada no token do cliente, descriptografada em memória por request).
- **TLS válido obrigatório** (Cowork rejeita self-signed) — via Let's Encrypt no Traefik.
- **Store de preferências** só com dados não-sensíveis (sem chave, sem PII além do `user_id`/email do Clockify).
- Chave de criptografia do token off-repo (env var), com plano de rotação.
- Reaproveitar as decisões de auth/tenancy do PGBrain (per-token, flat authz).

---

## 11. Riscos

| Risco | Mitigação |
|---|---|
| **Bugs de OAuth do connector no Cowork** (loop about:blank #11814, persistência #52565, falha pós-auth #291) | **PoC (Passo 1)** valida cedo; espelhar o PGBrain que já trilha esse caminho. |
| **Rate-limit do Let's Encrypt** em `*.hstgr.cloud` (pegou o PGIntegra) | PGBrain conseguiu cert válido; confirmar na PoC; fallback = coordenar com o time da VPS. |
| Atualização do plugin (casca) no Cowork é por org owner / por commit | Lógica fica no **servidor** (deploy independente, chega na hora); só a casca usa o "Update" do marketplace. |
| Reescrever `learned`/config de arquivo-local → store-por-usuário | Lógica pura já testada; adaptar a camada de persistência. |

---

## 12. Testing strategy (resumo)

- **Núcleo de IO** (clockify_api/ics/entries/bizdays/resolução): manter/portar os testes Python atuais (respx para HTTP). Resolução leve ganha testes de busca direcionada + cache.
- **OAuth/token:** testes de emissão/validação do JWT (cripto da chave, claims), e do fluxo well-known/DCR/PKCE.
- **Preferências:** testes do store por-usuário (upsert learned, default).
- **Smoke de deploy:** healthcheck do container + TLS válido + 1 chamada MCP autenticada.
- Detalhar via skill `testing-strategy` no plano.

---

## 13. Fora de escopo (esta entrega)

- **`/clockify-report`** (diário/mensal, live artifact on-brand) → **fase 2**.
- **Claude Code** (terminal) → abandonado; CLI/hook/lockstep removidos.
- Integração Microsoft Graph para calendário (substituir o ICS) → futuro opcional.
