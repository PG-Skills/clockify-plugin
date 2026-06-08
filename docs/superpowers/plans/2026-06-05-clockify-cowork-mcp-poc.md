# PoC OAuth — clockify-mcp no Cowork · Plano de implementação (v2, simples)

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development` ou `superpowers:executing-plans`. Steps usam checkbox (`- [ ]`).

**Goal:** provar, no Cowork, que um MCP server próprio (FastMCP) com **OAuth mínimo** e a chave do Clockify **cifrada no token (stateless)** funciona ponta a ponta e **persiste entre sessões** — com o **mínimo de partes possível**.

**Princípio (diretriz do usuário):** **simplicidade > robustez.** Onboarding de 1 passo, uso fácil. **Cortado:** RS256/JWKS, rate-limit, tenancy, validações de segurança elaboradas. **Mantido:** só o essencial pro Cowork aceitar e pro leigo usar.

**Tech Stack:** Python 3.12, `fastmcp` 3.4, `httpx`, `cryptography` (AES-GCM), `pyjwt` (**HS256** — issuer==verifier, basta), `pytest`+`respx`. Deploy: Docker + Traefik (espelha o PGBrain).

**Já validado (spike `docs/superpowers/spikes/2026-06-05-oauth-stateless/`):** o provider OAuth stateless + refresh (C3), `get_access_token().claims` (C1), e que o FastMCP expõe as rotas OAuth + 401/`WWW-Authenticate` sozinho. Este plano formaliza o spike em produto + adiciona a página `/connect`, a casca do plugin e o deploy.

**Gate (Task 6):** no Cowork — instalar → autorizar (colar a chave) → `whoami` responde → **fechar/reabrir → segue autenticado** (cruzando a expiração do token, não só "reabrir rápido").

---

## File Structure

`server/` na raiz do repo. Reaproveita o código já validado no spike.

```
server/
  pyproject.toml                 # fastmcp, httpx, cryptography, pyjwt
  .env.example                   # CLOCKIFY_TOKEN_KEY, JWT_SECRET, PUBLIC_URL, CLOCKIFY_MCP_DOMAIN
  Dockerfile
  docker-compose.yml             # espelha PGBrain (rede própria + label Traefik)
  src/clockify_mcp/
    __init__.py
    crypto.py                    # encrypt_key/decrypt_key (do spike) + jwt mint/decode
    clockify.py                  # async get_user(api_key)
    auth.py                      # StatelessClockifyOAuth (do spike) + página /connect
    app.py                       # FastMCP(auth=...) + tool whoami
    serve.py                     # entrypoint HTTP (bind 0.0.0.0:8080)
  tests/                         # do spike + Client(server) integration
clockify-cowork/                 # casca do plugin pro Cowork (separada do v1.0)
  .claude-plugin/plugin.json
  .mcp.json                      # connector remoto
  commands/clockify-tracking.md  # (stub na PoC; conteúdo na Fundação)
```

---

## Task 1: Núcleo determinístico (crypto + clockify) — portar do spike

**Files:** `server/pyproject.toml`, `server/src/clockify_mcp/{crypto,clockify}.py`, `server/tests/{test_crypto,test_clockify}.py`

- [ ] **Step 1:** copiar `crypto.py` e o cliente `get_user` do spike (`docs/superpowers/spikes/2026-06-05-oauth-stateless/prototype.py` → funções `enc`/`dec` viram `encrypt_key`/`decrypt_key`; `clockify.py` é o `get_user` com header `X-Api-Key` + `GET /user`, levantando `ValueError` em 401). Código já validado no spike.
- [ ] **Step 2:** testes: `test_crypto.py` (roundtrip + falha com chave errada) e `test_clockify.py` (respx: 200 → identidade; 401 → ValueError). Ver os testes do spike.
- [ ] **Step 3:** `cd server && uv run pytest -q` → PASS.
- [ ] **Step 4:** `git add server/ && git commit -m "feat(server): crypto + clockify client (portado do spike validado)"`

## Task 2: Provider OAuth stateless + tool `whoami`

**Files:** `server/src/clockify_mcp/{auth,app}.py`, `server/tests/test_auth.py`

- [ ] **Step 1:** portar `StatelessClockifyOAuth` do spike (`prototype.py`) para `auth.py`. É o provider com `authorize/load_authorization_code/exchange_authorization_code/load_refresh_token/exchange_refresh_token/verify_token/register_client`, JWT HS256, `ck` cifrado no token e no refresh. **Sem RS256, sem rate-limit, sem tenancy.**
- [ ] **Step 2:** `app.py` — `FastMCP(name="clockify-mcp", auth=provider)` + tool `whoami` que lê a chave via `get_access_token().claims["ck"]` → `decrypt_key` → `get_user` (código do `app.py` do spike, já validado).
- [ ] **Step 3:** `test_auth.py` — portar `test_prototype.py` (ciclo authorize→code→access→**refresh** preserva a chave sem texto; token adulterado → None). **Acrescentar** o teste de integração via `Client`/ASGI: rotas well-known 200, `POST /mcp` sem token → 401 com `WWW-Authenticate` (provado no spike).
- [ ] **Step 4:** `cd server && uv run pytest -q` → PASS. Commit.

## Task 3: Página `/connect` (coleta a chave) — a parte nova

> O spike provou tudo MENOS a página interativa. Aqui o `authorize` redireciona para `/connect`; o form coleta a chave; o POST valida (`get_user`), emite o `code` (carregando `ck`) e redireciona pro `redirect_uri` do cliente.

**Files:** `server/src/clockify_mcp/auth.py` (rotas custom), `server/tests/test_connect.py`

- [ ] **Step 1:** implementar `authorize(client, params)` para assinar os params (redirect_uri, state, code_challenge, client_id) num "txn" HS256 e retornar `f"{PUBLIC_URL}/connect?txn=..."`.
- [ ] **Step 2:** rota `GET /connect` → HTML mínimo (1 campo: chave do Clockify, com link "onde pegar: canto superior direito → Preferences → Advanced → Generate"; o ICS fica pra Fundação). Rota `POST /connect` → valida a chave (`get_user`), `mint_authorization_code(uid, key, params, client_id)`, redireciona `302` para `redirect_uri?code=...&state=...`. Registrar as rotas via o mecanismo de custom routes do FastMCP (`@app.custom_route` / `additional_http_routes` — confirmar a API exata da 3.4 no momento; é o único ponto de descoberta restante).
- [ ] **Step 3:** `test_connect.py` (ASGI httpx): `GET /connect` → 200 e contém o campo; `POST /connect` com chave válida (respx mock do Clockify) → 302 com `code`+`state`; chave inválida → reapresenta o form com erro.
- [ ] **Step 4:** `cd server && uv run pytest -q` → PASS. Commit.

## Task 4: Casca do plugin pro Cowork (C4 — sem isso o gate não roda)

**Files:** `clockify-cowork/.claude-plugin/plugin.json`, `clockify-cowork/.mcp.json`, `clockify-cowork/commands/clockify-tracking.md`

- [ ] **Step 1:** `plugin.json` — nome `clockify-cowork` (NÃO colidir com o v1.0 `clockify-plugin` publicado), version `0.1.0`, `commands` + `mcpServers` apontando pro `.mcp.json`.
- [ ] **Step 2:** `.mcp.json` — declara o connector remoto:
  ```json
  { "mcpServers": { "clockify": { "type": "http", "url": "https://clockify.srv1625247.hstgr.cloud/mcp" } } }
  ```
  (confirmar a chave/forma exata que o Cowork espera pra connector OAuth remoto — item de descoberta junto da Task 6.)
- [ ] **Step 3:** `commands/clockify-tracking.md` — stub mínimo na PoC ("rode `whoami` pra confirmar a conexão"); o fluxo de lançamento é da Fundação.
- [ ] **Step 4:** `git add clockify-cowork/ && git commit -m "feat(cowork): casca do plugin com connector MCP remoto"`

## Task 5: Deploy (espelha o PGBrain — C5 era falso positivo)

**Files:** `server/{Dockerfile,docker-compose.yml,.env.example,src/clockify_mcp/serve.py}`

- [ ] **Step 1:** `serve.py` — `from app import mcp; mcp.run(transport="http", host="0.0.0.0", port=8080)` (bind **0.0.0.0** — corrige W3; default do FastMCP é 127.0.0.1, que o Traefik não alcança).
- [ ] **Step 2:** `Dockerfile` — `python:3.12-slim`; `pip install uv`; `uv pip install --system .` (adicionar `[build-system] hatchling` + `[tool.hatch.build.targets.wheel] packages=["src/clockify_mcp"]` no pyproject — corrige W5); `CMD ["python","-m","clockify_mcp.serve"]`; HEALTHCHECK em `/.well-known/oauth-authorization-server` (existe sem auth).
- [ ] **Step 3:** `docker-compose.yml` — **copiar o padrão exato do PGBrain** (`AI_Team/PGBrain/docker-compose.yml`): `name: clockify-mcp`, rede **própria** `clockify-net` (`driver: bridge`, NÃO external), labels `traefik.docker.network=clockify-net` + `Host(\`${CLOCKIFY_MCP_DOMAIN}\`)` + `entrypoints=websecure` + `tls.certresolver=letsencrypt` + `loadbalancer.server.port=8080`, **sem `ports:`**, `mem_limit: 512m`, bind 0.0.0.0.
- [ ] **Step 4:** `.env.example` — `CLOCKIFY_MCP_DOMAIN=clockify.srv1625247.hstgr.cloud`, `PUBLIC_URL=https://clockify.srv1625247.hstgr.cloud`, `CLOCKIFY_TOKEN_KEY=` (base64 32B), `JWT_SECRET=` (token hex). Comando de geração no comentário.
- [ ] **Step 5 (manual, com o usuário):** deploy na VPS espelhando o runbook do PGBrain (`scp` → `/docker/clockify-mcp/` → `.env` → `docker compose up -d --build`). ⚠️ **NÃO tocar `/docker/traefik/`** (compartilhado: PGIntegra/PGBrain/Nexus). Confirmar TLS: `curl -sI https://clockify.srv1625247.hstgr.cloud/.well-known/oauth-authorization-server` → 200. Se LE falhar (rate-limit `*.hstgr.cloud`), coordenar com o time da VPS.
- [ ] **Step 6:** commit dos arquivos de deploy.

## Task 6: Gate no Cowork (manual — só o usuário)

- [ ] Add marketplace (repo da casca `clockify-cowork`) → instalar.
- [ ] 1ª ação → navegador abre `/connect` → colar a chave → autorizar.
- [ ] Rodar `whoami` → "Conectado como <nome>".
- [ ] **Fechar e reabrir o Cowork** (idealmente após o token expirar — ou setar `expires_in` curto num teste de staging) → `whoami` de novo → **sem** recolar a chave (prova o refresh, C3).
- [ ] Registrar resultado + bugs de plataforma no `HANDOFF.md`. **PASS → plano da Fundação. FAIL → reavaliar.**

---

## Self-Review (v2)

- **Diretriz de simplicidade aplicada:** HS256 (não RS256/JWKS), sem rate-limit/tenancy, onboarding 1 passo. ✓
- **CRITICALs do plan-critic:** C1 (`get_access_token().claims`) ✓ validado no spike; C2 (`Client`/ASGI) ✓ no spike + Task 2; C3 (refresh com `ck`) ✓ validado; C4 (casca `.mcp.json`) → Task 4 nova; **C5 = falso positivo** (rede própria + label é o padrão do PGBrain, verificado). W3 (bind 0.0.0.0) e W5 (build-system) → Task 5.
- **Descoberta restante (mínima):** API de custom routes do FastMCP 3.4 (Task 3) e a forma exata do `.mcp.json` pra connector OAuth remoto no Cowork (Task 4/6). Tudo o resto é código já rodando.

## Fora de escopo da PoC
Fluxo de `/clockify-tracking`, resolução leve, store de preferências, branding final da página, i18n, ICS. → Fundação, após a PoC passar.
