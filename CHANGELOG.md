# Changelog

Mudanças relevantes do plugin **clockify-plugin** (marketplace `pg-clockify`).
Segue [semver](https://semver.org). A `version` é fixada em **lockstep** no
`clockify-plugin/.claude-plugin/plugin.json` e em `.claude-plugin/marketplace.json`.

## [1.0.1] — 2026-06-08

### Mudou
- **Cópia local do CLI condicionada à versão.** No Cowork o terminal não enxerga a pasta do
  plugin, então a skill espelha os `.py` em `.clockify/bin/`. Antes recopiava **toda sessão**;
  agora grava um marcador `.clockify/bin/.cli-version` e **só recopia quando a `version` do
  plugin muda** — sessões seguintes na mesma pasta rodam direto, sem recopiar. (Exige bump de
  versão a cada release, o que também aciona o botão "Atualizar" do Cowork.)

## [1.0.0] — 2026-06-08

Primeira versão **consolidada e versionada**. Arquitetura **local** (sem servidor, sem OAuth):
skill conversacional + CLI Python zero-dependência (stdlib) lendo `.clockify/` na pasta do
projeto aberta no Cowork.

### Funcionalidades
- **`/clockify`** — **único ponto de setup**: cola a API key e conecta a **agenda do Outlook
  (obrigatória)**; ao final, um **manual rápido de boas-vindas** com exemplos práticos.
- **`/clockify-tracking`** — lança horas (hoje / um dia / um período), puxando reuniões da
  agenda do Outlook, com anti-duplicata por bloco e preferências aprendidas.
- **`/clockify-report`** — relatório **diário** (um mês, dia a dia) e **mensal** (intervalo
  ≤ 12 meses), com **resumo** (média + dia/mês mais cheio), **horas por projeto** e, no
  diário, **lacunas** (dias úteis sem registro).

### Guard de pasta configurada
- `setup-status` (CLI, local, sem rede): `tracking` e `report` só rodam numa pasta totalmente
  configurada pelo `/clockify`. Sem config → orienta a rodar `/clockify` ali ou abrir, no
  Cowork, a pasta correta. Agenda do Outlook passou a ser **obrigatória** ("configurado" =
  chave + ICS).

### Consolidação
- Renomeado de `clockify-cowork` → **`clockify-plugin`** (diretório, manifestos e docs).
- Plugin CLI antigo (`clockify-horas`) removido do marketplace `pg-clockify`.
