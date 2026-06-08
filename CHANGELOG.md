# Changelog

Mudanças relevantes do plugin **clockify-plugin** (marketplace `pg-clockify`).
Segue [semver](https://semver.org). A `version` é fixada em **lockstep** no
`clockify-plugin/.claude-plugin/plugin.json` e em `.claude-plugin/marketplace.json`.

## [1.0.0] — 2026-06-08

Primeira versão **consolidada e versionada**. Arquitetura **local** (sem servidor, sem OAuth):
skill conversacional + CLI Python zero-dependência (stdlib) lendo `.clockify/` na pasta do
projeto aberta no Cowork.

### Funcionalidades
- **`/clockify`** — conexão/onboarding (cola a API key uma vez; agenda do Outlook opcional) e,
  ao final, um **manual rápido de boas-vindas** com exemplos práticos.
- **`/clockify-tracking`** — lança horas (hoje / um dia / um período), puxando reuniões da
  agenda do Outlook quando conectada, com anti-duplicata por bloco e preferências aprendidas.
- **`/clockify-report`** — relatório **diário** (um mês, dia a dia) e **mensal** (intervalo
  ≤ 12 meses), agora com **resumo** (média + dia/mês mais cheio), **horas por projeto** e, no
  diário, **lacunas** (dias úteis sem registro).

### Consolidação
- Renomeado de `clockify-cowork` → **`clockify-plugin`** (diretório, manifestos e docs).
- Plugin CLI antigo (`clockify-horas`) removido do marketplace `pg-clockify`.
