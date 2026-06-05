# clockify-mcp — servidor MCP remoto (Cowork)

MCP server que lança horas no Clockify pelo **Claude Cowork**, conversando em linguagem
natural. É um **OAuth Authorization Server stateless**: a pessoa cola a chave do Clockify
uma vez numa página da PG e nunca mais — a chave viaja **cifrada (AES-GCM) dentro do token**
e o servidor **nunca a guarda**.

No ar: `https://clockify.srv1625247.hstgr.cloud/mcp` (VPS PG, atrás do Traefik compartilhado).

## Arquitetura

```
Cowork ──OAuth (Bearer)──► clockify-mcp (FastMCP, Python)
  1ª vez: navegador → /connect (cola a chave + ICS opcional, página com a marca PG)
                       │ chave/ICS cifrados na "identidade" → embutidos no token
  tools ──► resolve.py (busca direcionada) ──► API REST do Clockify
        └─► ics.py (agenda Outlook) · prefs.py (SQLite: atividade padrão + aprendidas)
```

- **Identidade única no token** (`auth.py`): `{uid, ck, ws, ics}` viaja inteira em todos os
  elos da cadeia OAuth (code → access → refresh) — sobrevive ao silent-refresh.
- **Resolução leve** (`resolve.py`): busca por nome (`strict-name-search`), nunca lista o
  workspace inteiro (o `meta` pesado estourava o timeout do Cowork).
- **Store de preferências** (`prefs.py`): SQLite por `user_id`, só dados não-sensíveis (a
  chave nunca entra). Volume `clockify-data` (persiste entre redeploys).
- **Tools idioma-neutras**: devolvem dados; o Claude verbaliza na língua do usuário.

## Módulos (`src/clockify_mcp/`)
`auth.py` OAuth AS · `crypto.py` AES-GCM + JWT · `context.py` UserContext/request_context ·
`clockify.py` client async · `pure.py` lógica pura (UTC, dias úteis) · `ics.py` agenda ·
`prefs.py` SQLite · `resolve.py` resolução + add_entries · `tools.py` as 9 tools · `app.py`
FastMCP + página /connect · `serve.py` entrypoint.

## Dev local
```bash
cd server
uv sync
uv run pytest -q          # 71 testes
uv run ruff check .
PUBLIC_URL=http://localhost:8080 CLOCKIFY_TOKEN_KEY=$(python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())") JWT_SECRET=$(openssl rand -hex 32) uv run python -m clockify_mcp.serve
```

## Deploy (VPS — espelha o PGBrain)
```bash
rsync -az --delete --exclude=.venv --exclude=__pycache__ --exclude=.env ./ pg-openclaw:/docker/clockify-mcp/
ssh pg-openclaw 'cd /docker/clockify-mcp && docker compose up -d --build'
# smoke: curl -sI https://clockify.srv1625247.hstgr.cloud/.well-known/oauth-authorization-server  → 200 (LE)
```
- **Secrets** (`/docker/clockify-mcp/.env`, off-repo): `CLOCKIFY_TOKEN_KEY` (base64 32B),
  `JWT_SECRET` (hex 32), `CLOCKIFY_MCP_DOMAIN`, `PREFS_DB=/data/prefs.db`.
- ⚠️ **NUNCA** tocar `/docker/traefik/` (compartilhado: PGIntegra/PGBrain/Nexus/OpenClaw/n8n).
- Rede própria `clockify-net`, sem `ports:` publicados, `mem_limit 512m`.

## Segurança
Chave do Clockify nunca em repouso (só cifrada no token + em memória por request). HS256
(issuer==verifier). SQLite parametrizado. `ics_url` validado (https + rejeita IPs privados,
sem follow-redirect) contra SSRF. Fail-fast se secrets ausentes em produção.

## Fora de escopo (fase 2)
`/clockify-report` (relatórios diário/mensal). Cache de resolução, escala horizontal.
