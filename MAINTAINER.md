# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-cowork` e o **marketplace** `pg-clockify`.

## Cortar um release

> **Política de versão (pré-lançamento, atual):** o `plugin.json` e a entrada no
> `marketplace.json` estão **sem o campo `version`** — de propósito. Sem `version`, o Claude
> trackeia atualização pelo **commit SHA**, então **todo push** no branch é detectado pelo botão
> **"Atualizar"** (`/plugin update`). É o que queremos durante a iteração: cada correção chega
> sem bumpar nada. **Quando lançar pra valer**, aí sim fixe uma `version` (semver) nos dois
> pontos (`clockify-cowork/.claude-plugin/plugin.json` e a entrada em
> `.claude-plugin/marketplace.json`) e bumpe em **lockstep** a cada release.

1. Faça as mudanças e rode os testes: `cd clockify-cowork/scripts && python3 -m pytest -q`.
2. `git commit` + `git push` para o branch principal.
   > **Push via 2.ª conta:** use o `.envrc` na raiz do repo (que exporta `GH_TOKEN` e configura
   > o remote com o token da conta de publicação). Não remover nem editar o `.envrc`.
3. Cada pessoa pega a atualização pelo botão **"Atualizar"** (ou `/plugin update
   clockify-cowork@pg-clockify`). Como não há `version` fixa, o update vem por commit.

## Como um colega instala (primeira vez)

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-cowork@pg-clockify
/clockify
```

O `/clockify` faz o onboarding: pede a API key, valida e salva em `.clockify/credentials.json`
na pasta do projeto. Nenhuma dependência extra além do Claude desktop app.

## Validação local

```
cd clockify-cowork/scripts
python3 -m pytest -q          # testes unitários (stdlib only)

claude plugin validate clockify-cowork    # valida o plugin
claude plugin validate .                  # valida o marketplace
claude --plugin-dir clockify-cowork       # carrega o plugin numa sessão de teste
```
