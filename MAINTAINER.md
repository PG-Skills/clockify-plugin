# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-plugin` e o **marketplace** `pg-clockify`.

## Cortar um release

> **Política de versão (pré-lançamento):** enquanto o plugin **não** for lançado para os
> colegas, tudo permanece em **`1.0.0`** — não faça bump a cada mudança. O versionamento em
> lockstep abaixo vale a partir do **primeiro lançamento de verdade**. Em dev, atualize o
> binário local com `uv tool install --force --reinstall plugins/clockify-plugin` (rebuild
> limpo independe da versão).

1. Faça as mudanças e rode (dentro de `plugins/clockify-plugin/`): `uv run pytest -q && uv run ruff check . && uv run pyright`.
2. Bump da versão em **lockstep** nos cinco pontos (semver, mesma versão em todos):
   `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (entrada do plugin),
   `plugins/clockify-plugin/pyproject.toml`, `plugins/clockify-plugin/src/clockify_plugin/__init__.py`
   e `plugins/clockify-plugin/tests/test_smoke.py` (asserção de `__version__`).
   O SessionStart hook (`scripts/ensure_cli.py`) lê o `version` do `plugin.json` para decidir
   reinstalar a CLI — então o bump do `plugin.json` é o que faz o colega receber o código novo;
   manter os outros quatro alinhados é o que mantém tudo coerente em 1.0.0, 1.1.0, etc.
   (v1.0 usa `learned.json` por-usuário, não versionado — as "atividades aprendidas" que
   substituem o antigo `history.json` e a seção `overrides`. A atividade padrão é opcional.)
3. `git commit` + `git push` para o branch principal.
4. Avise a equipe. Cada pessoa atualiza com `/plugin marketplace update` seguido de
   `/plugin update clockify-plugin@pg-clockify`. Na próxima sessão, o SessionStart hook
   reinstala a CLI (guard de versão detecta o novo `version`).

## Como um colega instala (primeira vez)

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-plugin@pg-clockify
/clockify-setup
```

A CLI Python é instalada automaticamente pelo SessionStart hook (`scripts/ensure_cli.py`,
rodado via `uv run --script`) com `uv tool install`. Cross-platform (macOS/Windows/Linux);
requer apenas `uv` no PATH.

## Validação local

```
claude plugin validate plugins/clockify-plugin   # valida o plugin
claude plugin validate .                        # valida o marketplace
claude --plugin-dir plugins/clockify-plugin      # carrega o plugin do subdiretório numa sessão de teste
```
