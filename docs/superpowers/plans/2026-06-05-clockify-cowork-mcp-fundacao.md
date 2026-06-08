# Fundação clockify-mcp — Plano de implementação v2 (lançar horas no Cowork)

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:subagent-driven-development` ou `superpowers:executing-plans`. Steps usam checkbox (`- [ ]`).

**Goal:** dar ao MCP server (já no ar) as ferramentas + a skill que lançam horas no Clockify pelo Cowork, conversando em linguagem natural — portando o fluxo do v1.0.

**Architecture:** tools MCP no `server/` leem um `UserContext` (chave + user_id + workspace_id + ics_url) de uma **identidade única** que viaja cifrada no token OAuth, e chamam um **client Clockify async** com **resolução direcionada**. Preferências num **SQLite por user_id** (volume persistente). A conversa (skill `/clockify-tracking`) orquestra; as tools devolvem **dados idioma-neutros**.

**Tech Stack:** Python 3.12, fastmcp 3.4, httpx async, sqlite3 (stdlib), icalendar + recurring-ical-events, pytest+respx. Reusa lógica **pura** do v1.0.

**DIRETRIZ MESTRE:** simplicidade > robustez, leigos. Cortado: cache, tela de workspace, abstração pra escala, `list_projects`, `set_default` no onboarding.

**v2 (pós plan-critic):** resolve C-1/C-2 (identidade única na cadeia de token, sobrevive ao refresh), W-1 (resolução via aprendida/padrão), W-2 (`strict-name-search=true`), W-3 (volume p/ SQLite).

---

## Contratos-chave

**C1+C2 — Identidade única que flui pela cadeia inteira (resolve os 2 CRITICAL).**
Hoje `auth.py` espalha `uid`/`ck` por **7 elos** (mint_authorization_code, load_authorization_code.subject, exchange_authorization_code, _issue [access+refresh], load_refresh_token.subject, exchange_refresh_token, verify_token.claims). Adicionar `ws`/`ics` campo a campo = esquecer um e o claim evapora no refresh.
**Solução (regra ÚNICA, mata o campo-a-campo de vez):** o `identity = {"uid","ck","ws","ics"}` é **uma chave única** em todo lugar. Nunca reconstruir campo a campo:
- `crypto.mint(...)` body = `{"typ": t, "identity": identity, "cid": cid, "sc": scopes}` (a identity é UMA chave, nunca `**identity`).
- `verify_token`: `claims = d["identity"]` (NÃO `{"uid": d["uid"], ...}` — esse era o elo de leitura que quebrava).
- `AuthorizationCode`/`RefreshToken` `subject = json.dumps(identity)`; `exchange_*`: `identity = json.loads(subject)`.
- `_issue(cid, identity, scopes)` recebe e re-emite o dict; `mint_authorization_code(identity, txn)`.
Adicionar campo = só incluir no dict no `/connect` e ler no `request_context`. **Zero elo campo-a-campo.**
`ck` e `ics` cifrados (AES-GCM); `uid` e `ws` em claro (não-sensíveis). `ics` pode ser `None` (cifra só no `/connect`, nunca sobre `None`).

**C2b — client async.** Novo `clockify.py` async: `get_user` (devolve `workspace_id` de `defaultWorkspace`/`activeWorkspace`), `entries(start,end)`, `create_entry(payload)`, `search_projects(name)`, `tasks_in_project(pid,name)`, `search_tags(name)`. Funções **puras** portadas textualmente do v1.0: `to_utc_iso`, janelas UTC, `business_days`, parse ICS.

**C3 — resolução direcionada + W-1 (sem regressão pro leigo).** O endpoint de tasks do Clockify **exige projectId** → não há busca global de tarefa. Para o leigo recorrente NÃO sentir isso:
- a **skill** resolve nome→`project` via **atividade aprendida/padrão** (que já guardam `project`) ANTES de chamar `resolve_activity`;
- `resolve_activity(name, project)` exige `project`; se ausente e houver ambiguidade → erro `AMBIGUO` + candidatos (o Claude pergunta).
Busca: `projects?name=X&strict-name-search=true` (valor `"true"` explícito — W-2) → `projectId` → `projects/{pid}/tasks?name=Y&strict-name-search=true`; tags `tags?name=`.
`add_entries(items)`: chama `entries` (anti-duplicata) → resolve-então-grava **item a item, para no 1º erro** → `{gravados, total, falhou_em, motivo}`. Dedupe por **`(data_local, taskId)`** (não por nome — W-N4).

---

## File Structure (server/)
```
server/src/clockify_mcp/
  context.py     # UserContext + request_context() — NOVO
  clockify.py    # client ASYNC (reescrito) + get_user devolve ws
  pure.py        # to_utc_iso, janelas UTC, business_days — NOVO (porta v1.0)
  ics.py         # fetch+parse ICS async — NOVO (porta v1.0)
  prefs.py       # SQLite: defaults + learned por user_id — NOVO
  resolve.py     # resolve_activity direcionada + dedupe — NOVO
  tools.py       # tools MCP — NOVO
  auth.py        # REFATORAR p/ identity dict único (C1+C2)
  app.py         # whoami → dict; /connect monta identity (+ ICS opcional)
  settings.py    # + PREFS_DB; fail-fast se secret ausente em prod (N-1)
clockify-cowork/commands/clockify-tracking.md
server/docker-compose.yml   # + volume clockify-data:/data (W-3)
```

---

## Task 1: refatorar auth p/ identidade única (C1+C2; resolve C-NEW-1/2)
**Files:** `auth.py`, `clockify.py` (get_user — **nesta task**, C-NEW-2), `context.py` (novo), `app.py` (/connect), `tests/test_identity.py`, **`tests/test_core.py` (reconciliar o refresh test, W-NEW-1)**
- [ ] **Step 1 (teste de regressão — o coração, lado de LEITURA):** emitir p/ `identity={uid,ck,ws,ics}` → `verify_token(access).claims` tem os 4 → **`exchange_refresh_token` → `verify_token(novo access).claims["ws"]` e `["ics"]` SOBREVIVEM** (lê `claims`, não o body mintado; pós-refresh, não só o 1º access). `ics=None` também roundtrip. `request_context()` → `UserContext(api_key=decrypt(ck), user_id=uid, workspace_id=ws, ics_url=decrypt(ics) if ics else None)`. **Atualizar `test_core.py::test_oauth_cycle_stateless_with_refresh`** para o shape novo (`claims["identity"]`/`claims["ck"]`) — não deixar o teste antigo passando com o contrato velho (false green).
- [ ] **Step 2 (regra da chave única — ver Contratos):** refatorar `auth.py` para `identity` como **uma chave** no JWT: `mint` body `{"typ":t,"identity":identity,"cid":cid,"sc":scopes}`; `verify_token` `claims = d["identity"]`; `subject = json.dumps(identity)` nos `load_*`; `exchange_*` `identity = json.loads(subject)`; `_issue(cid, identity, scopes)`; `mint_authorization_code(identity, txn)`. **Nesta mesma task**, `clockify.get_user` passa a devolver `workspace_id = d.get("defaultWorkspace") or d.get("activeWorkspace")` (não depender da Task 2). `/connect` (`connect_submit`) monta `identity = {"uid":user["id"], "ck":encrypt(key), "ws":user["workspace_id"], "ics":encrypt(ics_url) if ics_url else None}` e chama `mint_authorization_code(identity, txn)`. `context.py` novo.
- [ ] **Step 3:** `uv run pytest -q` + e2e `/tmp/oauth_flow_test.py` (que faz refresh — confirma `ws`/`ics` na prática). Commit.

## Task 2: client async + lógica pura (C2b, W-2)
**Files:** `clockify.py`, `pure.py` (novo), `tests/test_clockify_io.py`, `tests/test_pure.py`
- [ ] **Step 1 (teste):** `pure` = casos de `test_entries.py`/`test_bizdays.py` do v1.0. `search_projects`/`tasks_in_project`/`search_tags` com respx — **assertar `params["strict-name-search"]=="true"`**. `entries`/`create_entry` com respx.
- [ ] **Step 2:** portar `to_utc_iso`/janelas (de `entries.py`) e `business_days` (de `bizdays.py`) p/ `pure.py` (sem `self`). Client async (espelha `get_user`), `params={"name":n,"strict-name-search":"true"}`.
- [ ] **Step 3:** pytest. Commit.

## Task 3: ICS async
**Files:** `ics.py` (porta de v1.0), `pyproject.toml` (+ icalendar, recurring-ical-events), `tests/test_ics.py`
- [ ] **Step 1 (teste):** fixtures de `test_ics.py` v1.0 (recorrência + ignora CANCELLED).
- [ ] **Step 2:** porta async (GET, não HEAD). Adicionar deps no `pyproject` **e rodar `uv lock`** (N-1).
- [ ] **Step 3:** pytest. Commit.

## Task 4: store SQLite + volume (W-3)
**Files:** `prefs.py` (novo), `settings.py` (PREFS_DB), `docker-compose.yml` (volume), `.env.example`, `tests/test_prefs.py`
- [ ] **Step 1 (teste):** `set_default`/`get_prefs` roundtrip; `learn` upsert por `(uid, _norm(match))`; user vazio → {}.
- [ ] **Step 2:** SQLite (`PREFS_DB`, default `/data/prefs.db`), tabelas `defaults`/`learned`, `ON CONFLICT DO UPDATE`, WAL, conexão por-chamada. Reusar só `_norm` de `learned.py`. **Sem cache.** Adicionar `prefs_db` ao `Settings` (frozen dataclass) em `from_env`. **Fail-fast (N-1):** se `PUBLIC_URL` não é localhost e `JWT_SECRET`/`CLOCKIFY_TOKEN_KEY` ausentes → `raise` em `get_settings()` (hoje cai em default inseguro).
- [ ] **Step 3 (W-3):** `docker-compose.yml`: `volumes: [clockify-data:/data]` no service + bloco `volumes: { clockify-data: { name: clockify-data } }`. `PREFS_DB=/data/prefs.db` no `.env.example`.
- [ ] **Step 4:** pytest. Commit.

## Task 5: resolução direcionada + dedupe (C3, W-1)
**Files:** `resolve.py` (novo), `tests/test_resolve.py`
- [ ] **Step 1 (teste):** `resolve_activity("X")` 2 projetos → `AMBIGUO`+candidatos; **com `project` fornecido → resolve sem `AMBIGUO`** (guard do W-1: aprendida/padrão fornecem o project); `add_entries` para no 1º erro → `{gravados,total,falhou_em}`; dedupe omite item cujo `(data_local, taskId)` já está nas `entries`.
- [ ] **Step 2:** implementar C3. `add_entries` chama `entries` antes de gravar.
- [ ] **Step 3:** pytest. Commit.

## Task 6: tools MCP idioma-neutras (N-2)
**Files:** `tools.py` (novo), `app.py`, `tests/test_tools.py`, **`tests/test_core.py`+`tests/test_integration.py` (atualizar `whoami`)**
- [ ] **Step 1 (teste):** cada tool com `request_context` mockado → devolve **dados** (datas ISO, ids), nunca frase.
- [ ] **Step 2:** registrar tools em `app.mcp` via `request_context()`. `whoami` → `{name,email}` (muda de `str`→`dict`). **Atualizar os testes da PoC** que assertavam a string `"Conectado como…"`.
- [ ] **Step 3:** suite inteira. Commit.

## Task 7: skill `/clockify-tracking` + onboarding leigo
**Files:** `clockify-cowork/commands/clockify-tracking.md`, `app.py` (/connect: + campo ICS opcional, multilíngue), `clockify-cowork/.claude-plugin/plugin.json` (bump)
- [ ] **Step 1:** reescrever o command (porta de `lancar.md`+`lancar-dias.md`): escolha dia/período → reconhecer (**aprendida→padrão fornecem o `project` p/ a resolução** — W-1) → conferir → gravar; **na língua do usuário**; anti-duplicata explícita. Mensagens leigas: sem token, chave inválida, token expirado/reconectar.
- [ ] **Step 2:** `/connect`: campo **ICS opcional** + multilíngue por `Accept-Language`.
- [ ] **Step 3:** commit.

## Task 8: deploy + verificação
- [ ] suite verde + ruff; `rsync` → VPS → `docker compose up -d --build`; smoke: 401, /connect, fluxo OAuth e2e + **um `add_entries` real contra conta de teste** + **W-3: gravar pref → redeploy → pref sobrevive (volume)**.
- [ ] **NÃO tocar `/docker/traefik/`.** Outras 6 stacks intactas.

---

## Decisões registradas
- **Token expirado:** refresh silencioso (PoC provou). Reconexão só se refresh falhar.
- **Resolução global por nome (v1.0) → por (projeto,tarefa):** trade-off **consciente**; o leigo recorrente não sente porque aprendida/padrão fornecem o projeto (W-1). Documentar no command.
- **Single-instance by design** (SQLite local + sem cache): correto p/ time interno PG.

## Fora de escopo
`/clockify-report` (fase 2), cache de resolução, multi-workspace UI, escala horizontal.
