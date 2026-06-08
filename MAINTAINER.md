# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-plugin` e o **marketplace** `pg-clockify`.

## Cortar um release

> **Política de versão (versionado por release):** o `plugin.json` e a entrada no
> `marketplace.json` carregam uma `version` semver **fixada em lockstep** (atual: ver
> `CHANGELOG.md`). Com `version` fixa, o Claude só
> oferece **"Atualizar"** quando o número **sobe** — **pushar commit sem bumpar não atualiza
> ninguém** (`/plugin update` reporta "já está na última versão"). A cada release, **bumpe a
> `version` nos dois pontos** (`clockify-plugin/.claude-plugin/plugin.json` e a entrada em
> `.claude-plugin/marketplace.json`) seguindo semver (MAJOR breaking / MINOR feature / PATCH
> fix) e registre no `CHANGELOG.md`.

1. Faça as mudanças e rode os testes: `cd clockify-plugin/scripts && python3 -m pytest -q`.
2. **Bumpe a `version`** (semver) em lockstep no `plugin.json` e no `marketplace.json`, e
   anote no `CHANGELOG.md`.
3. `git commit` + `git push` para o branch principal.
   > **Push via 2.ª conta:** use o `.envrc` na raiz do repo (que exporta `GH_TOKEN` e configura
   > o remote com o token da conta de publicação). Não remover nem editar o `.envrc`.
4. (Opcional) crie a tag `vX.Y.Z` e dê push da tag.
5. Cada pessoa pega a atualização pelo botão **"Atualizar"** (ou `/plugin update
   clockify-plugin@pg-clockify`) — só aparece se a `version` subiu.

## Como um colega instala (primeira vez)

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-plugin@pg-clockify
/clockify
```

O `/clockify` faz **todo o setup**: pede a API key e conecta a **agenda do Outlook (obrigatória)**,
salvando em `.clockify/credentials.json` na pasta do projeto. `/clockify-tracking` e
`/clockify-report` só rodam numa pasta já configurada. Nenhuma dependência extra além do Claude
desktop app.

## Validação local

```
cd clockify-plugin/scripts
python3 -m pytest -q          # testes unitários (stdlib only)

claude plugin validate clockify-plugin    # valida o plugin
claude plugin validate .                  # valida o marketplace
claude --plugin-dir clockify-plugin       # carrega o plugin numa sessão de teste
```
