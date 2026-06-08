# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-cowork` e o **marketplace** `pg-clockify`.

## Cortar um release

> **Política de versão (pré-lançamento):** enquanto o plugin **não** for lançado para os
> colegas, tudo permanece em **`1.0.0`** — não faça bump a cada mudança. O versionamento em
> lockstep abaixo vale a partir do **primeiro lançamento de verdade**.

1. Faça as mudanças e rode os testes: `cd clockify-cowork/scripts && python3 -m pytest -q`.
2. Bump da versão em **lockstep** nos dois pontos (semver, mesma versão em ambos):
   `.claude-plugin/marketplace.json` (entrada do plugin) e
   `clockify-cowork/.claude-plugin/plugin.json`.
3. `git commit` + `git push` para o branch principal.
   > **Push via 2.ª conta:** use o `.envrc` na raiz do repo (que exporta `GH_TOKEN` e configura
   > o remote com o token da conta de publicação). Não remover nem editar o `.envrc`.
4. Avise a equipe. Cada pessoa atualiza com `/plugin marketplace update` seguido de
   `/plugin update clockify-cowork@pg-clockify`.

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
