# Spike — OAuth stateless para o clockify-mcp (validação local)

**Data:** 2026-06-05 · **Veredito: VIÁVEL** (validado na máquina, sem o Cowork).

Protótipo que prova, empiricamente, o ponto mais arriscado do redesenho: um **MCP server
próprio (FastMCP) como OAuth Authorization Server**, com a **chave do Clockify embutida
criptografada no token** (stateless), funcionando — **incluindo o refresh** (o CRITICAL C3
do plan-critic). Rodar: `cd <este dir> && uv run pytest -q` (precisa de `fastmcp httpx
cryptography pyjwt pytest respx pytest-asyncio`).

## O que foi PROVADO

1. **FastMCP 3.4.0 suporta AS custom completo.** `OAuthProvider` expõe `authorize`,
   `exchange_authorization_code`, `exchange_refresh_token`, `load_*`, `verify_token`,
   `register_client`. Submódulo `cimd` (Client ID Metadata Documents — sucessor do DCR).
2. **Design stateless funciona** (`prototype.py` + `test_prototype.py`, 2 testes verdes):
   - `AccessToken.claims` (dict) e `RefreshToken/AuthorizationCode.subject` carregam o `ck`
     (chave do Clockify cifrada em AES-GCM). O server **nunca guarda a chave**.
   - **C3 RESOLVIDO:** `exchange_refresh_token` re-emite o access token **a partir do `ck`
     do próprio refresh token** — o Cowork renova sem recoletar a chave. Provado por
     `test_key_survives_full_oauth_cycle_stateless`.
   - A chave **nunca aparece em texto** no token (só o blob cifrado). Token adulterado → rejeitado.
3. **Integração com o server (`app.py`):** montando `FastMCP(auth=provider)`, o FastMCP expõe
   sozinho: `/.well-known/oauth-authorization-server` (200), `/authorize`, `/token`,
   `/.well-known/oauth-protected-resource/...` e `/mcp`. **`POST /mcp` sem token → 401 com
   `WWW-Authenticate: Bearer ... resource_metadata=...`** (RFC 9728) — o handshake que o
   Cowork usa pra iniciar o OAuth.
4. **C1 corrigido:** a tool lê a chave via `get_access_token().claims["ck"]` (idiomático),
   **não** o contextvar global inseguro do plano original.

## O que FALTA (não validável aqui)

- A **página `/connect`** interativa (form que coleta a chave + redirect com o `code`) — a
  mecânica de code/token está provada; a UI/fluxo HTTP interativo não foi montado.
- O **Cowork real** (Add marketplace → autorizar → whoami → persiste após restart) — só o
  usuário consegue testar; risco residual = bugs de plataforma do connector OAuth.
- **Deploy na VPS** + TLS LE no subdomínio + a rede correta do Traefik compartilhado.

## Notas para a implementação real

- `resource_base_url` vs mount path: no protótipo o protected-resource saiu como
  `.../oauth-protected-resource/mcp/mcp` (duplicação de `/mcp`) — ajustar `resource_base_url`/
  mount pra não duplicar.
- HS256 aqui é só protótipo → **RS256/ES256 em produção** (`RSAKeyPair`); reconciliar com o
  WARNING W1 do plan-critic (o "rejeitar HS*" só vale quando verifier aceita alg do atacante;
  aqui o issuer == verifier).
- Há provider `supabase` embutido no FastMCP — alternativa se algum dia quisermos AS gerenciado
  (mas não resolve a chave do Clockify por si; ver decisão no spec).
