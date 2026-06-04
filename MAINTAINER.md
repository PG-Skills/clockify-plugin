# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-horas` e o **marketplace** `pg-clockify`.

## Cortar um release

1. Faça as mudanças e rode (dentro de `plugins/clockify-horas/`): `uv run pytest -q && uv run ruff check . && uv run pyright`.
2. Bump da versão em **lockstep** nos quatro pontos (semver, mesma versão em todos):
   `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (entrada do plugin),
   `plugins/clockify-horas/pyproject.toml` e `plugins/clockify-horas/src/clockify_horas/__init__.py`.
   O SessionStart hook (`scripts/ensure_cli.py`) lê o `version` do `plugin.json` para decidir
   reinstalar a CLI — então o bump do `plugin.json` é o que faz o colega receber o código novo;
   manter os outros três alinhados é o que mantém tudo coerente em 1.0.0, 1.1.0, etc.
3. `git commit` + `git push` para o branch principal.
4. Avise a equipe. Cada pessoa atualiza com `/plugin marketplace update` seguido de
   `/plugin update clockify-horas@pg-clockify`. Na próxima sessão, o SessionStart hook
   reinstala a CLI (guard de versão detecta o novo `version`).

## Como um colega instala (primeira vez)

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-horas@pg-clockify
/clockify-setup
```

A CLI Python é instalada automaticamente pelo SessionStart hook (`scripts/ensure_cli.py`,
rodado via `uv run --script`) com `uv tool install`. Cross-platform (macOS/Windows/Linux);
requer apenas `uv` no PATH.

## Validação local

```
claude plugin validate plugins/clockify-horas   # valida o plugin
claude plugin validate .                        # valida o marketplace
claude --plugin-dir plugins/clockify-horas      # carrega o plugin do subdiretório numa sessão de teste
```
