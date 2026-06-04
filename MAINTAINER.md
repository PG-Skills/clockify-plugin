# Manutenção (mantenedor)

Este repo é, ao mesmo tempo, o **plugin** `clockify-horas` e o **marketplace** `pg-clockify`.

## Cortar um release

1. Faça as mudanças e rode `uv run pytest -q && uv run ruff check . && uv run pyright`.
2. Bump da versão em `.claude-plugin/plugin.json` (campo `version`, semver). **Esta é a
   fonte única da versão**: o SessionStart hook (`scripts/ensure_cli.py`) lê exatamente esse
   campo para decidir reinstalar a CLI. Bump aqui = colega recebe o código novo na próxima
   sessão. (O `version` do `pyproject.toml` é interno e não precisa casar; mantenha alinhado
   só por clareza.)
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
claude plugin validate .
claude --plugin-dir .   # carrega o plugin do diretório atual numa sessão de teste
```
