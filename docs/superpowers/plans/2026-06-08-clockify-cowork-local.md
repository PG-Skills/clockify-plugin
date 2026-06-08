# clockify-cowork local (skill + CLI zero-dep) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lançar horas no Clockify pelo Cowork usando uma skill conversacional + um CLI Python **zero-dependência** que lê credencial/preferências de arquivos locais na pasta do projeto (persistem), sem VPS, sem OAuth, sem servidor.

**Architecture:** O plugin `clockify-cowork` contém uma **skill** (cérebro: conversa i18n, decide, verbaliza) e um **CLI stdlib** (braço: fala com a API REST do Clockify via `urllib`, devolve JSON idioma-neutro). Estado em `.clockify/` na pasta do projeto (`credentials.json` + `prefs.json`), gitignored. Reusa a lógica refinada de `server/src/clockify_mcp/` (busca direcionada, anti-duplicata por dia, UTC) portada de async/`httpx` para sync/`urllib`.

**Tech Stack:** Python 3.12 **somente stdlib** em runtime (`urllib`, `json`, `argparse`, `datetime`, `zoneinfo`); `pytest` só em dev. Skill/commands em Markdown.

---

## File Structure

```
clockify-cowork/
├── .claude-plugin/plugin.json        # MODIFICAR: remover mcpServers
├── .mcp.json                          # REMOVER (não há mais connector remoto)
├── commands/
│   ├── clockify-tracking.md          # MODIFICAR: tool calls → CLI subcommands
│   └── clockify.md                    # MODIFICAR: status/onboarding via CLI
├── skills/
│   └── clockify-tracking/
│       └── SKILL.md                   # CRIAR: cérebro conversacional (i18n)
└── scripts/
    ├── pyproject.toml                 # CRIAR: dev-only (pytest, pythonpath)
    ├── clockify_cli/
    │   ├── __main__.py                # CRIAR: entrypoint fino
    │   ├── cli.py                     # CRIAR: argparse + dispatch + JSON out
    │   ├── config.py                  # CRIAR: paths + credentials.json
    │   ├── prefs.py                   # CRIAR: prefs.json (default + learned)
    │   ├── pure.py                    # CRIAR: cópia verbatim de server pure.py
    │   ├── http_json.py               # CRIAR: helper urllib (GET/POST JSON)
    │   ├── clockify.py                # CRIAR: client sync (porta de httpx→urllib)
    │   └── resolve.py                 # CRIAR: resolve + add_entries sync
    └── tests/
        ├── test_pure.py
        ├── test_config.py
        ├── test_prefs.py
        ├── test_http_json.py
        ├── test_clockify.py
        ├── test_resolve.py
        └── test_cli.py
```

**Invocação no Cowork:** `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli <subcomando> [args]`. Como o diretório `clockify_cli/` tem `__main__.py`, o Python o executa com `sys.path[0]` = o próprio diretório → imports planos (`import config`) funcionam sem `PYTHONPATH`. Pytest usa `pythonpath = ["clockify_cli"]` (definido no `pyproject.toml`).

---

## Task 0: Passo 0 — Confirmar execução no sandbox do Cowork (manual, GATE)

**Objetivo:** validar a premissa de runtime ANTES de escrever código. Não é TDD — é um teste manual no Cowork que decide o mecanismo de invocação.

- [ ] **Step 1: Rodar o sondador no Cowork**

No app do Cowork, com um projeto (pasta local) aberto, cole:

> Rode no terminal e me mostre a saída literal:
> ```
> echo "PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT:-<vazio>}"
> echo "PROJECT_DIR=${CLAUDE_PROJECT_DIR:-<vazio>}"
> pwd
> python3 -c "import sys,urllib.request,json,zoneinfo; print('stdlib OK', sys.version.split()[0])"
> mkdir -p .clockify && echo '{"hello":1}' > .clockify/_probe.json && cat .clockify/_probe.json
> ```

- [ ] **Step 2: Interpretar e registrar a decisão**

Anote no topo deste plano (uma linha) qual caminho vale:
- Se `python3 ... stdlib OK` imprimiu → runtime confirmado (esperado).
- Se `CLAUDE_PLUGIN_ROOT` veio preenchido E aponta para um caminho legível no terminal → **invocação A**: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli ...`.
- Se `CLAUDE_PLUGIN_ROOT` vazio/inacessível → **invocação B (fallback)**: a skill copia `scripts/clockify_cli/` para `.clockify/bin/` na 1ª execução e roda `python3 .clockify/bin/clockify_cli ...`. Ajustar a SKILL.md (Task 9) conforme o resultado.
- Se `CLAUDE_PROJECT_DIR` veio preenchido → usar como base de `.clockify/`; senão, usar `pwd`/cwd (já coberto pela precedência em `config.py`).

- [ ] **Step 3: Limpar o probe**

> Rode: `rm -f .clockify/_probe.json`

**Critério de saída:** runtime Python stdlib confirmado + caminho de invocação (A ou B) decidido. Se Python não rodar no sandbox (improvável — já rodou em 2026-06-05), PARAR e reavaliar a arquitetura.

---

## Task 1: Scaffold do pacote CLI

**Files:**
- Create: `clockify-cowork/scripts/pyproject.toml`
- Create: `clockify-cowork/scripts/clockify_cli/__main__.py`
- Create: `clockify-cowork/scripts/clockify_cli/cli.py`

- [ ] **Step 1: Criar `pyproject.toml` (dev-only)**

```toml
[project]
name = "clockify-cli"
version = "0.1.0"
description = "CLI zero-dependência (stdlib) que lança horas no Clockify a partir do Cowork"
requires-python = ">=3.12"
dependencies = []

[dependency-groups]
dev = ["pytest>=8"]

[tool.pytest.ini_options]
pythonpath = ["clockify_cli"]
testpaths = ["tests"]
```

- [ ] **Step 2: Criar `cli.py` com dispatch mínimo (só `--help`/sem args)**

```python
"""Dispatch do CLI. Cada subcomando imprime JSON em stdout (idioma-neutro) e
retorna um código de saída (0 = ok, !=0 = erro). A skill conversacional
interpreta o JSON; o CLI nunca escreve frase pronta pro usuário."""

import argparse
import json
import sys


def _emit(obj, stream) -> None:
    json.dump(obj, stream, ensure_ascii=False)
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clockify_cli")
    p.add_subparsers(dest="cmd")
    return p


def main(argv=None, *, stdout=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.cmd:
        parser.print_help(stdout)
        return 0
    _emit({"error": "UNKNOWN_COMMAND", "cmd": args.cmd}, stdout)
    return 2
```

- [ ] **Step 3: Criar `__main__.py`**

```python
import sys

import cli

raise SystemExit(cli.main(sys.argv[1:]))
```

- [ ] **Step 4: Rodar e verificar**

Run: `cd clockify-cowork/scripts && python3 clockify_cli`
Expected: imprime o help do argparse, exit 0.

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/pyproject.toml clockify-cowork/scripts/clockify_cli/__main__.py clockify-cowork/scripts/clockify_cli/cli.py
git commit -m "feat(cli): scaffold do CLI clockify zero-dependência"
```

---

## Task 2: `pure.py` (cópia verbatim) + testes

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/pure.py`
- Test: `clockify-cowork/scripts/tests/test_pure.py`

- [ ] **Step 1: Escrever os testes (falham — módulo não existe)**

```python
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pure

TZ = ZoneInfo("America/Sao_Paulo")


def test_to_utc_iso_converts_local_to_utc_z():
    dt = datetime(2026, 1, 28, 9, 0, tzinfo=TZ)  # 09:00 BRT = 12:00Z
    assert pure.to_utc_iso(dt) == "2026-01-28T12:00:00Z"


def test_to_utc_iso_requires_aware():
    import pytest
    with pytest.raises(ValueError):
        pure.to_utc_iso(datetime(2026, 1, 28, 9, 0))


def test_day_window_utc_covers_local_day():
    start, end = pure.day_window_utc(date(2026, 1, 28), TZ)
    assert start == "2026-01-28T03:00:00Z"  # 00:00 BRT = 03:00Z
    assert end == "2026-01-29T03:00:00Z"


def test_range_window_utc_inclusive():
    start, end = pure.range_window_utc(date(2026, 1, 28), date(2026, 1, 30), TZ)
    assert start == "2026-01-28T03:00:00Z"
    assert end == "2026-01-31T03:00:00Z"  # 00:00 do dia seguinte a end


def test_business_days_skips_weekend():
    dias = pure.business_days(date(2026, 1, 30), date(2026, 2, 2))  # sex..seg
    assert [d.isoformat() for d in dias] == ["2026-01-30", "2026-02-02"]


def test_business_days_rejects_inverted_range():
    import pytest
    with pytest.raises(ValueError):
        pure.business_days(date(2026, 2, 2), date(2026, 1, 30))
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_pure.py -q`
Expected: FAIL (ModuleNotFoundError: pure).

- [ ] **Step 3: Criar `pure.py` (cópia verbatim de `server/src/clockify_mcp/pure.py`)**

Copiar o conteúdo EXATO do arquivo `server/src/clockify_mcp/pure.py` (já é stdlib puro: `to_utc_iso`, `day_window_utc`, `range_window_utc`, `business_days`). Nenhuma alteração.

```bash
cp server/src/clockify_mcp/pure.py clockify-cowork/scripts/clockify_cli/pure.py
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_pure.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/pure.py clockify-cowork/scripts/tests/test_pure.py
git commit -m "feat(cli): pure.py (UTC/janelas/dias úteis) + testes"
```

---

## Task 3: `config.py` (paths + credentials.json)

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/config.py`
- Test: `clockify-cowork/scripts/tests/test_config.py`

- [ ] **Step 1: Escrever os testes (falham)**

```python
import json

import config


def test_base_dir_prefers_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path / "x"))
    assert config.base_dir() == tmp_path / "x"


def test_base_dir_uses_project_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("CLOCKIFY_DIR", raising=False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    assert config.base_dir() == tmp_path / ".clockify"


def test_base_dir_falls_back_to_cwd(monkeypatch, tmp_path):
    monkeypatch.delenv("CLOCKIFY_DIR", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert config.base_dir() == tmp_path / ".clockify"


def test_load_credentials_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    assert config.load_credentials() is None


def test_save_then_load_credentials(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="KEY", ics_url=None, workspace_id="ws1", user_id="u1")
    creds = config.load_credentials()
    assert creds == {"api_key": "KEY", "ics_url": None, "workspace_id": "ws1", "user_id": "u1"}
    # gravado no caminho esperado
    assert json.loads((tmp_path / "credentials.json").read_text())["api_key"] == "KEY"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_config.py -q`
Expected: FAIL (ModuleNotFoundError: config).

- [ ] **Step 3: Implementar `config.py`**

```python
"""Localização e leitura/escrita do estado local em `.clockify/`.

Precedência da base: CLOCKIFY_DIR (env) > $CLAUDE_PROJECT_DIR/.clockify > ./.clockify.
`credentials.json` é o único arquivo sensível (api_key); fica sob `.clockify/`,
que DEVE estar no .gitignore."""

import json
import os
from pathlib import Path

CREDENTIALS_FILE = "credentials.json"


def base_dir() -> Path:
    env = os.environ.get("CLOCKIFY_DIR")
    if env:
        return Path(env)
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        return Path(project) / ".clockify"
    return Path.cwd() / ".clockify"


def _credentials_path() -> Path:
    return base_dir() / CREDENTIALS_FILE


def load_credentials() -> dict | None:
    p = _credentials_path()
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def save_credentials(
    *,
    api_key: str,
    ics_url: str | None,
    workspace_id: str | None,
    user_id: str | None = None,
) -> None:
    d = base_dir()
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "api_key": api_key,
        "ics_url": ics_url,
        "workspace_id": workspace_id,
        "user_id": user_id,
    }
    _credentials_path().write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
```

> `user_id` (não-sensível) é cacheado junto do `workspace_id` para o caminho quente
> (`entries`/`add`) não precisar de uma chamada extra a `get_user` — ver Task 8.

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_config.py -q`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/config.py clockify-cowork/scripts/tests/test_config.py
git commit -m "feat(cli): config.py (paths + credentials.json) + testes"
```

---

## Task 4: `prefs.py` (prefs.json: default + learned)

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/prefs.py`
- Test: `clockify-cowork/scripts/tests/test_prefs.py`

- [ ] **Step 1: Escrever os testes (falham)**

```python
import config
import prefs


def test_get_prefs_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    assert prefs.get_prefs() == {"default": {}, "learned": []}


def test_set_default_then_get(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.set_default(project="Proj X", task="Dev", tag=None, billable=True, daily_target=8.0)
    d = prefs.get_prefs()["default"]
    assert d["project"] == "Proj X" and d["billable"] is True and d["daily_target"] == 8.0


def test_learn_upsert_normalizes_case_and_space(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.learn("Daily", project="Equipe", task="Inovação", tag=None, billable=None)
    prefs.learn("  daily ", project="Equipe", task="Daily", tag=None, billable=False)  # upsert
    learned = prefs.get_prefs()["learned"]
    assert len(learned) == 1  # 'Daily' e '  daily ' são a MESMA chave (normalizada)
    assert learned[0]["task"] == "Daily" and learned[0]["match"] == "daily"


def test_forget_learned_normalizes(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.learn("Daily", project="P", task=None, tag=None, billable=None)
    assert prefs.forget_learned("  DAILY ") is True   # normaliza ao esquecer
    assert prefs.forget_learned("daily") is False
    assert prefs.get_prefs()["learned"] == []


def test_clear_resets_default_and_learned(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs.set_default(project="P", task=None, tag=None, billable=None, daily_target=None)
    prefs.learn("x", project="P", task=None, tag=None, billable=None)
    prefs.clear()
    assert prefs.get_prefs() == {"default": {}, "learned": []}
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_prefs.py -q`
Expected: FAIL (ModuleNotFoundError: prefs).

- [ ] **Step 3: Implementar `prefs.py`**

```python
"""Preferências locais (não-sensíveis) em `.clockify/prefs.json`:
atividade padrão (`default`) + atividades aprendidas (`learned`, upsert por `match`).
Espelha a semântica do prefs do servidor, mas em arquivo JSON simples."""

import json

import config

PREFS_FILE = "prefs.json"


def _path():
    return config.base_dir() / PREFS_FILE


def get_prefs() -> dict:
    p = _path()
    if not p.exists():
        return {"default": {}, "learned": []}
    data = json.loads(p.read_text(encoding="utf-8"))
    data.setdefault("default", {})
    data.setdefault("learned", [])
    return data


def _save(data: dict) -> None:
    d = config.base_dir()
    d.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _clean(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _norm(match: str) -> str:
    """Normaliza a palavra-chave (strip + lower) — PARIDADE com server/prefs.py:_norm.
    Garante que 'Daily', 'daily' e '  daily ' colidam (dedup no learn) e sejam
    esquecíveis (forget). Sem isso, case/espaço criam duplicatas e órfãos."""
    return match.strip().lower()


def set_default(*, project, task, tag, billable, daily_target) -> None:
    data = get_prefs()
    data["default"] = _clean(
        {
            "project": project,
            "task": task,
            "tag": tag,
            "billable": billable,
            "daily_target": daily_target,
        }
    )
    _save(data)


def learn(match: str, *, project, task, tag, billable) -> None:
    data = get_prefs()
    key = _norm(match)
    entry = _clean(
        {"match": key, "project": project, "task": task, "tag": tag, "billable": billable}
    )
    learned = [e for e in data["learned"] if e.get("match") != key]  # upsert por match_norm
    learned.append(entry)
    data["learned"] = learned
    _save(data)


def forget_learned(match: str) -> bool:
    key = _norm(match)
    data = get_prefs()
    before = len(data["learned"])
    data["learned"] = [e for e in data["learned"] if e.get("match") != key]
    removed = len(data["learned"]) < before
    if removed:
        _save(data)
    return removed


def clear() -> None:
    _save({"default": {}, "learned": []})
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_prefs.py -q`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/prefs.py clockify-cowork/scripts/tests/test_prefs.py
git commit -m "feat(cli): prefs.py (default + learned em prefs.json) + testes"
```

---

## Task 5: `http_json.py` (helper urllib)

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/http_json.py`
- Test: `clockify-cowork/scripts/tests/test_http_json.py`

- [ ] **Step 1: Escrever os testes (falham)**

```python
import io
import json

import pytest

import http_json


class _FakeResp:
    def __init__(self, status, payload):
        self.status = status
        self._raw = json.dumps(payload).encode()

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_request_json_get_ok(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["api_key"] = req.headers.get("X-api-key")
        return _FakeResp(200, {"name": "Ana"})

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    data = http_json.request_json(
        "GET", "https://api.clockify.me/api/v1/user", api_key="KEY"
    )
    assert data == {"name": "Ana"}
    assert captured["method"] == "GET"
    assert captured["api_key"] == "KEY"


def test_request_json_params_in_querystring(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        return _FakeResp(200, [])

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    http_json.request_json(
        "GET", "https://x/y", api_key="K", params={"name": "Proj X", "strict-name-search": "true"}
    )
    assert "name=Proj+X" in captured["url"] and "strict-name-search=true" in captured["url"]


def test_request_json_post_sends_body(monkeypatch):
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["body"] = req.data
        captured["ct"] = req.headers.get("Content-type")
        return _FakeResp(201, {"id": "e1"})

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    out = http_json.request_json("POST", "https://x/y", api_key="K", body={"a": 1})
    assert out == {"id": "e1"}
    assert json.loads(captured["body"]) == {"a": 1}
    assert captured["ct"] == "application/json"


def test_request_json_raises_httperror_on_4xx(monkeypatch):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(http_json, "urlopen", fake_urlopen)
    with pytest.raises(http_json.HttpError) as ei:
        http_json.request_json("GET", "https://x/y", api_key="K")
    assert ei.value.status == 401
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_http_json.py -q`
Expected: FAIL (ModuleNotFoundError: http_json).

- [ ] **Step 3: Implementar `http_json.py`**

```python
"""Helper HTTP JSON sobre urllib (stdlib) — substitui httpx do servidor.

`request_json` faz GET/POST com header X-Api-Key, querystring opcional e corpo JSON,
e levanta `HttpError(status)` em respostas >= 400 (equivalente ao raise_for_status)."""

import json
import urllib.error
import urllib.parse
from urllib.request import Request, urlopen  # urlopen é patchado nos testes


class HttpError(Exception):
    def __init__(self, status: int, body: str = ""):
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def request_json(method, url, *, api_key, params=None, body=None, timeout=30.0):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    headers = {"X-Api-Key": api_key}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        raise HttpError(e.code, detail) from e
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_http_json.py -q`
Expected: PASS (4 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/http_json.py clockify-cowork/scripts/tests/test_http_json.py
git commit -m "feat(cli): http_json.py (urllib GET/POST JSON) + testes"
```

---

## Task 6: `clockify.py` (client sync, porta de httpx→urllib)

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/clockify.py`
- Test: `clockify-cowork/scripts/tests/test_clockify.py`

- [ ] **Step 1: Escrever os testes (falham)** — paridade com `server/tests` (mock de `http_json.request_json`)

```python
import pytest

import clockify
import http_json


def _patch(monkeypatch, handler):
    """handler(method, url, params, body) -> retorno de request_json."""
    def fake(method, url, *, api_key, params=None, body=None, timeout=30.0):
        return handler(method, url, params, body)
    monkeypatch.setattr(clockify.http_json, "request_json", fake)


def test_get_user_ok(monkeypatch):
    _patch(monkeypatch, lambda m, u, p, b: {
        "id": "u1", "name": "Ana", "email": "ana@pg.com", "defaultWorkspace": "ws1"
    })
    out = clockify.get_user("KEY")
    assert out == {"id": "u1", "name": "Ana", "email": "ana@pg.com", "workspace_id": "ws1"}


def test_get_user_invalid_key_raises_valueerror(monkeypatch):
    for status in (401, 403):  # 401/403 = chave inválida ou sem permissão
        def handler(m, u, p, b, _s=status):
            raise http_json.HttpError(_s)
        _patch(monkeypatch, handler)
        with pytest.raises(ValueError):
            clockify.get_user("BAD")


def test_get_user_other_http_error_propagates(monkeypatch):
    def handler(m, u, p, b):
        raise http_json.HttpError(500)
    _patch(monkeypatch, handler)
    with pytest.raises(http_json.HttpError):
        clockify.get_user("KEY")


def test_search_projects_uses_strict_name(monkeypatch):
    seen = {}
    def handler(m, u, p, b):
        seen.update(p or {})
        return [{"id": "p1", "name": "Proj X"}]
    _patch(monkeypatch, handler)
    out = clockify.search_projects("K", "ws1", "Proj X")
    assert out[0]["id"] == "p1"
    assert seen == {"name": "Proj X", "strict-name-search": "true"}


def test_entries_paginates(monkeypatch):
    calls = {"n": 0}
    def handler(m, u, p, b):
        calls["n"] += 1
        # página 1 cheia (200), página 2 incompleta -> para
        return [{"id": f"e{calls['n']}"}] * 200 if calls["n"] == 1 else [{"id": "last"}]
    _patch(monkeypatch, handler)
    out = clockify.entries("K", "ws1", "u1", "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z")
    assert calls["n"] == 2
    assert len(out) == 201


def test_create_entry_posts(monkeypatch):
    seen = {}
    def handler(m, u, p, b):
        seen["method"] = m
        seen["body"] = b
        return {"id": "e1"}
    _patch(monkeypatch, handler)
    out = clockify.create_entry("K", "ws1", {"description": "x"})
    assert out == {"id": "e1"} and seen["method"] == "POST" and seen["body"]["description"] == "x"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_clockify.py -q`
Expected: FAIL (ModuleNotFoundError: clockify).

- [ ] **Step 3: Implementar `clockify.py`** (mesma lógica do servidor, sync + http_json)

```python
"""Cliente Clockify síncrono (stdlib via http_json). Porta de server/clockify.py.

Diretriz mestre — simplicidade: NÃO lista o workspace inteiro (causava timeout). Cada
busca é por nome exato (`strict-name-search=true`), devolvendo só o match relevante."""

import http_json

BASE = "https://api.clockify.me/api/v1"
_PAGE_SIZE = 200
_STRICT_NAME = "true"


def _name_params(name: str) -> dict:
    return {"name": name, "strict-name-search": _STRICT_NAME}


def get_user(api_key: str) -> dict:
    """Valida a chave e retorna {id, name, email, workspace_id}. ValueError se inválida."""
    try:
        d = http_json.request_json("GET", f"{BASE}/user", api_key=api_key, timeout=10.0)
    except http_json.HttpError as e:
        if e.status in (401, 403):  # 401/403 = chave inválida ou sem permissão
            raise ValueError("chave do Clockify inválida") from e
        raise
    return {
        "id": d["id"],
        "name": d["name"],
        "email": d["email"],
        "workspace_id": d.get("defaultWorkspace") or d.get("activeWorkspace"),
    }


def search_projects(api_key: str, workspace_id: str, name: str) -> list[dict]:
    return http_json.request_json(
        "GET", f"{BASE}/workspaces/{workspace_id}/projects",
        api_key=api_key, params=_name_params(name), timeout=10.0,
    )


def tasks_in_project(api_key: str, workspace_id: str, project_id: str, name: str) -> list[dict]:
    return http_json.request_json(
        "GET", f"{BASE}/workspaces/{workspace_id}/projects/{project_id}/tasks",
        api_key=api_key, params=_name_params(name), timeout=10.0,
    )


def search_tags(api_key: str, workspace_id: str, name: str) -> list[dict]:
    return http_json.request_json(
        "GET", f"{BASE}/workspaces/{workspace_id}/tags",
        api_key=api_key, params=_name_params(name), timeout=10.0,
    )


def entries(api_key: str, workspace_id: str, user_id: str, start: str, end: str) -> list[dict]:
    """Time-entries crus na janela [start, end] (ISO UTC). GET paginado até página incompleta."""
    path = f"{BASE}/workspaces/{workspace_id}/user/{user_id}/time-entries"
    items: list[dict] = []
    page = 1
    while True:
        batch = http_json.request_json(
            "GET", path, api_key=api_key,
            params={"start": start, "end": end, "page": page, "page-size": _PAGE_SIZE},
        )
        items.extend(batch)
        if len(batch) < _PAGE_SIZE:
            return items
        page += 1


def create_entry(api_key: str, workspace_id: str, payload: dict) -> dict:
    return http_json.request_json(
        "POST", f"{BASE}/workspaces/{workspace_id}/time-entries",
        api_key=api_key, body=payload, timeout=10.0,
    )
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_clockify.py -q`
Expected: PASS (6 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/clockify.py clockify-cowork/scripts/tests/test_clockify.py
git commit -m "feat(cli): clockify.py (client sync via urllib) + testes"
```

---

## Task 7: `resolve.py` (resolve + add_entries sync)

**Files:**
- Create: `clockify-cowork/scripts/clockify_cli/resolve.py`
- Test: `clockify-cowork/scripts/tests/test_resolve.py`

- [ ] **Step 1: Escrever os testes (falham)** — cobre busca direcionada, anti-duplicata por dia e falha parcial

```python
import resolve


class FakeCl:
    """Substitui o módulo clockify nos testes (mesma assinatura)."""
    def __init__(self, projects=None, tasks=None, tags=None, existing=None):
        self._projects = projects or {}
        self._tasks = tasks or {}
        self._tags = tags or {}
        self.existing = existing or []
        self.created = []

    def search_projects(self, k, ws, name):
        return self._projects.get(name, [])

    def tasks_in_project(self, k, ws, pid, name):
        return self._tasks.get((pid, name), [])

    def search_tags(self, k, ws, name):
        return self._tags.get(name, [])

    def entries(self, k, ws, uid, start, end):
        return self.existing

    def create_entry(self, k, ws, payload):
        self.created.append(payload)
        return {"id": f"e{len(self.created)}"}


def test_resolve_requires_project(monkeypatch):
    monkeypatch.setattr(resolve, "cl", FakeCl())
    out = resolve.resolve_activity("K", "ws", name="Daily", project=None)
    assert out["status"] == "AMBIGUO" and out["motivo"] == "projeto necessário"


def test_resolve_ok(monkeypatch):
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )
    monkeypatch.setattr(resolve, "cl", fake)
    out = resolve.resolve_activity("K", "ws", name="Dev", project="Proj X")
    assert out == {"status": "OK", "project_id": "p1", "task_id": "t1", "tag_ids": []}


def test_resolve_ambiguous_project_returns_candidates(monkeypatch):
    fake = FakeCl(projects={"P": [{"id": "p1", "name": "P1"}, {"id": "p2", "name": "P2"}]})
    monkeypatch.setattr(resolve, "cl", fake)
    out = resolve.resolve_activity("K", "ws", name="Dev", project="P")
    assert out["status"] == "AMBIGUO" and [c["name"] for c in out["candidatos"]] == ["P1", "P2"]


def test_add_entries_skips_duplicates(monkeypatch):
    # já existe um entry no dia 2026-01-28 para task t1
    existing = [{"taskId": "t1", "timeInterval": {"start": "2026-01-28T12:00:00Z"}}]
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
        existing=existing,
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [{"description": "d", "date": "2026-01-28", "start": "09:00", "end": "10:00",
              "task": "Dev", "project": "Proj X"}]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert out["gravados"] == 0 and out["pulados_duplicata"] == 1 and fake.created == []


def test_add_entries_writes_and_stops_on_error(monkeypatch):
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},  # "Outra" não existe
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [
        {"description": "d1", "date": "2026-01-28", "start": "09:00", "end": "10:00",
         "task": "Dev", "project": "Proj X"},
        {"description": "d2", "date": "2026-01-28", "start": "10:00", "end": "11:00",
         "task": "Outra", "project": "Proj X"},
    ]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert out["gravados"] == 1 and out["falhou_em"] == 1 and out["motivo"] == "tarefa não encontrada"
    assert len(fake.created) == 1
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_resolve.py -q`
Expected: FAIL (ModuleNotFoundError: resolve).

- [ ] **Step 3: Implementar `resolve.py`** (porta sync de `server/resolve.py`; `cl` é o módulo `clockify`, mockável)

```python
"""Resolução direcionada (nome -> IDs) e gravação em lote com anti-duplicata.
Porta SÍNCRONA de server/resolve.py — mesma lógica, sem async. `cl` aponta para o
módulo clockify (substituível nos testes)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import clockify as cl
from pure import range_window_utc, to_utc_iso

_TZ = ZoneInfo("America/Sao_Paulo")


def _candidatos(items: list[dict]) -> list[dict]:
    return [{"id": it["id"], "name": it.get("name", "")} for it in items]


def resolve_activity(api_key, workspace_id, *, name, project=None, tag=None) -> dict:
    if project is None:
        return {"status": "AMBIGUO", "motivo": "projeto necessário", "candidatos": []}

    projs = cl.search_projects(api_key, workspace_id, project)
    if len(projs) == 0:
        return {"status": "NAO_ENCONTRADO", "motivo": "projeto não encontrado", "candidatos": []}
    if len(projs) > 1:
        return {"status": "AMBIGUO", "motivo": "projeto ambíguo", "candidatos": _candidatos(projs)}
    project_id = projs[0]["id"]

    tasks = cl.tasks_in_project(api_key, workspace_id, project_id, name)
    if len(tasks) == 0:
        return {"status": "NAO_ENCONTRADO", "motivo": "tarefa não encontrada", "candidatos": []}
    if len(tasks) > 1:
        return {"status": "AMBIGUO", "motivo": "tarefa ambígua", "candidatos": _candidatos(tasks)}
    task_id = tasks[0]["id"]

    tag_ids: list[str] = []
    if tag:
        tags = cl.search_tags(api_key, workspace_id, tag)
        if len(tags) == 0:
            return {"status": "NAO_ENCONTRADO", "motivo": "etiqueta não encontrada", "candidatos": []}
        if len(tags) > 1:
            return {"status": "AMBIGUO", "motivo": "etiqueta ambígua", "candidatos": _candidatos(tags)}
        tag_ids = [tags[0]["id"]]

    return {"status": "OK", "project_id": project_id, "task_id": task_id, "tag_ids": tag_ids}


def _local_dt(d: str, hhmm: str) -> datetime:
    return datetime.fromisoformat(f"{d}T{hhmm}").replace(tzinfo=_TZ)


def _entry_local_date(entry: dict) -> str | None:
    start = (entry.get("timeInterval") or {}).get("start")
    if not start:
        return None
    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    return dt.astimezone(_TZ).date().isoformat()


def add_entries(api_key, workspace_id, user_id, items: list[dict]) -> dict:
    total = len(items)
    if total == 0:
        return {"gravados": 0, "total": 0, "pulados_duplicata": 0, "falhou_em": None, "motivo": None}

    datas = [date.fromisoformat(it["date"]) for it in items]
    win_start, win_end = range_window_utc(min(datas), max(datas), _TZ)
    existentes = cl.entries(api_key, workspace_id, user_id, win_start, win_end)
    ja_existe: set[tuple[str, str]] = set()
    for e in existentes:
        d = _entry_local_date(e)
        tid = e.get("taskId")
        if d and tid:
            ja_existe.add((d, tid))

    gravados = 0
    pulados = 0
    for idx, item in enumerate(items):
        res = resolve_activity(
            api_key, workspace_id, name=item["task"], project=item.get("project"), tag=item.get("tag")
        )
        if res["status"] != "OK":
            return {"gravados": gravados, "total": total, "pulados_duplicata": pulados,
                    "falhou_em": idx, "motivo": res["motivo"]}

        chave = (item["date"], res["task_id"])
        if chave in ja_existe:
            pulados += 1
            continue

        payload = {
            "start": to_utc_iso(_local_dt(item["date"], item["start"])),
            "end": to_utc_iso(_local_dt(item["date"], item["end"])),
            "description": item.get("description", ""),
            "projectId": res["project_id"],
            "taskId": res["task_id"],
            "tagIds": res["tag_ids"],
            "billable": item.get("billable", False),
        }
        cl.create_entry(api_key, workspace_id, payload)
        gravados += 1
        ja_existe.add(chave)

    return {"gravados": gravados, "total": total, "pulados_duplicata": pulados,
            "falhou_em": None, "motivo": None}
```

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_resolve.py -q`
Expected: PASS (5 testes).

- [ ] **Step 5: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/resolve.py clockify-cowork/scripts/tests/test_resolve.py
git commit -m "feat(cli): resolve.py (resolução direcionada + anti-duplicata) + testes"
```

---

## Task 8: Subcomandos do CLI (wire em `cli.py`)

**Files:**
- Modify: `clockify-cowork/scripts/clockify_cli/cli.py`
- Test: `clockify-cowork/scripts/tests/test_cli.py`

Contrato de saída (JSON em stdout, idioma-neutro):
- `whoami` → `{"name","email","workspace_id"}` | `{"error":"NO_KEY"}` (exit 3) | `{"error":"INVALID_KEY"}` (exit 4). Em sucesso, **persiste** `workspace_id` no credentials.json (cache).
- `business-days --start --end` → `{"days":[ISO,...]}`.
- `entries --date | --start --end` → `{"entries":[...]}` (cru do Clockify).
- `resolve --name --project [--tag]` → repassa o dict de `resolve_activity`.
- `add --json - [--dry-run]` → lê lista de items de stdin; `--dry-run` devolve `{"dry_run":true,"items":[...]}` (sem rede de escrita); real repassa o dict de `add_entries`.
- `prefs get` → `get_prefs()`; `prefs set-default ...`/`prefs learn ...`/`prefs forget --match` → `{"ok":true,...}`.

- [ ] **Step 1: Escrever os testes (falham)** — chamam `cli.main([...], stdout=buf)` com rede mockada

```python
import io
import json

import cli
import clockify
import config
import prefs as prefs_mod
import resolve as resolve_mod


def _seed_creds(monkeypatch, tmp_path, **over):
    """Pré-popula credentials.json COMPLETO (api_key+workspace_id+user_id) para que o
    caminho quente NÃO chame get_user (rede). Reproduz o estado pós-whoami."""
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    base = {"api_key": "KEY", "ics_url": None, "workspace_id": "ws1", "user_id": "u1"}
    base.update(over)
    config.save_credentials(**base)


def _run(argv):
    buf = io.StringIO()
    code = cli.main(argv, stdout=buf)
    text = buf.getvalue()
    return code, (json.loads(text) if text.strip() else None)


def test_whoami_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["whoami"])
    assert code == 3 and out == {"error": "NO_KEY"}


def test_whoami_ok_caches_account(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="KEY", ics_url=None, workspace_id=None, user_id=None)
    monkeypatch.setattr(clockify, "get_user", lambda k: {
        "id": "u1", "name": "Ana", "email": "a@pg.com", "workspace_id": "ws1"})
    code, out = _run(["whoami"])
    assert code == 0 and out["name"] == "Ana"
    creds = config.load_credentials()
    assert creds["workspace_id"] == "ws1" and creds["user_id"] == "u1"  # cache de conta


def test_whoami_invalid_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="BAD", ics_url=None, workspace_id=None)
    def boom(k):
        raise ValueError("inválida")
    monkeypatch.setattr(clockify, "get_user", boom)
    code, out = _run(["whoami"])
    assert code == 4 and out == {"error": "INVALID_KEY"}


def test_business_days(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["business-days", "--start", "2026-01-30", "--end", "2026-02-02"])
    assert code == 0 and out == {"days": ["2026-01-30", "2026-02-02"]}


def test_entries_uses_cache_no_network(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    def boom(*a, **k):  # get_user NÃO pode ser chamado — cache completo
        raise AssertionError("get_user não deveria ser chamado")
    monkeypatch.setattr(clockify, "get_user", boom)
    monkeypatch.setattr(clockify, "entries", lambda key, ws, uid, s, e: [{"id": "e1"}])
    code, out = _run(["entries", "--date", "2026-01-28"])
    assert code == 0 and out == {"entries": [{"id": "e1"}]}


def test_add_dry_run_does_not_write(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    called = {"n": 0}
    monkeypatch.setattr(resolve_mod, "add_entries", lambda *a, **k: called.__setitem__("n", 1))
    payload = json.dumps([{"date": "2026-01-28", "start": "9:00", "end": "10:00",
                           "task": "Dev", "project": "Proj X"}])
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert code == 0 and out["dry_run"] is True and called["n"] == 0


def test_add_real_calls_add_entries_no_network(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    def boom(*a, **k):
        raise AssertionError("get_user não deveria ser chamado — cache completo")
    monkeypatch.setattr(clockify, "get_user", boom)
    monkeypatch.setattr(resolve_mod, "add_entries", lambda key, ws, uid, items: {
        "gravados": 1, "total": 1, "pulados_duplicata": 0, "falhou_em": None, "motivo": None})
    payload = json.dumps([{"date": "2026-01-28", "start": "9:00", "end": "10:00",
                           "task": "Dev", "project": "Proj X"}])
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-"])
    assert code == 0 and out["gravados"] == 1


def test_add_rejects_malformed_items(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    payload = json.dumps([{"date": "2026-01-28", "task": "Dev"}])  # falta start/end
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert code == 2 and out["error"] == "INVALID_ITEMS" and out["missing_at"] == [0]


def test_prefs_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    prefs_mod.learn("x", project="P", task=None, tag=None, billable=None)
    code, out = _run(["prefs", "reset"])
    assert code == 0 and out == {"ok": True}
    assert prefs_mod.get_prefs()["learned"] == []


def test_entries_invalid_key_incomplete_cache(monkeypatch, tmp_path):
    # cache incompleto (sem ws/uid) + chave ruim → INVALID_KEY estruturado, não traceback
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    config.save_credentials(api_key="BAD", ics_url=None, workspace_id=None, user_id=None)
    def boom(k):
        raise ValueError("inválida")
    monkeypatch.setattr(clockify, "get_user", boom)
    code, out = _run(["entries", "--date", "2026-01-28"])
    assert code == 4 and out == {"error": "INVALID_KEY"}


def test_add_rejects_non_list(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO('{"date":"2026-01-28"}'))  # objeto, não lista
    code, out = _run(["add", "--json", "-", "--dry-run"])
    assert code == 2 and out["error"] == "INVALID_ITEMS" and out["reason"] == "esperava_lista"
```

- [ ] **Step 2: Rodar — deve falhar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_cli.py -q`
Expected: FAIL (subcomandos ainda não existem).

- [ ] **Step 3: Implementar dispatch em `cli.py`** (substitui o corpo de `main`)

```python
"""Dispatch do CLI. Cada subcomando imprime JSON em stdout (idioma-neutro) e
retorna um código de saída (0=ok, 2=cmd desconhecido/items inválidos, 3=sem chave,
4=chave inválida, 5=erro de rede/HTTP). A skill conversacional interpreta o JSON; o CLI
nunca escreve frase pronta pro usuário."""

import argparse
import json
import sys

import clockify
import config
import http_json
import prefs as prefs_mod
import pure
import resolve as resolve_mod

EXIT_OK, EXIT_UNKNOWN, EXIT_NO_KEY, EXIT_INVALID_KEY, EXIT_HTTP = 0, 2, 3, 4, 5
_REQUIRED_ITEM_KEYS = {"date", "start", "end", "task"}


def _emit(obj, stream) -> None:
    json.dump(obj, stream, ensure_ascii=False)
    stream.write("\n")


def _load_key(stdout):
    creds = config.load_credentials()
    if not creds or not creds.get("api_key"):
        _emit({"error": "NO_KEY"}, stdout)
        return None
    return creds


def _account(creds, stdout):
    """(workspace_id, user_id) a partir do cache; só chama get_user se faltar algum
    (e re-cacheia). Mantém o caminho quente (entries/add/resolve) SEM rede quando a conta
    já foi resolvida no whoami/conexão (spec §4). Se PRECISAR chamar get_user e a chave for
    inválida (401/403), emite INVALID_KEY e retorna None — o chamador devolve
    EXIT_INVALID_KEY em vez de estourar traceback (cache incompleto + chave ruim)."""
    ws, uid = creds.get("workspace_id"), creds.get("user_id")
    if ws and uid:
        return ws, uid
    try:
        user = clockify.get_user(creds["api_key"])
    except ValueError:
        _emit({"error": "INVALID_KEY"}, stdout)
        return None
    config.save_credentials(
        api_key=creds["api_key"], ics_url=creds.get("ics_url"),
        workspace_id=user["workspace_id"], user_id=user["id"],
    )
    return user["workspace_id"], user["id"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="clockify_cli")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("whoami")

    bd = sub.add_parser("business-days")
    bd.add_argument("--start", required=True)
    bd.add_argument("--end", required=True)

    en = sub.add_parser("entries")
    en.add_argument("--date")
    en.add_argument("--start")
    en.add_argument("--end")

    rs = sub.add_parser("resolve")
    rs.add_argument("--name", required=True)
    rs.add_argument("--project")
    rs.add_argument("--tag")

    ad = sub.add_parser("add")
    ad.add_argument("--json", required=True, help="'-' para ler de stdin")
    ad.add_argument("--dry-run", action="store_true")

    pr = sub.add_parser("prefs")
    prs = pr.add_subparsers(dest="prefs_cmd")
    prs.add_parser("get")
    prs.add_parser("reset")
    sd = prs.add_parser("set-default")
    for f in ("project", "task", "tag"):
        sd.add_argument(f"--{f}")
    sd.add_argument("--billable", action=argparse.BooleanOptionalAction)  # --billable/--no-billable/ausente
    sd.add_argument("--daily-target", type=float)
    ln = prs.add_parser("learn")
    ln.add_argument("--match", required=True)
    ln.add_argument("--project", required=True)
    for f in ("task", "tag"):
        ln.add_argument(f"--{f}")
    ln.add_argument("--billable", action=argparse.BooleanOptionalAction)
    fg = prs.add_parser("forget")
    fg.add_argument("--match", required=True)
    return p


def main(argv=None, *, stdout=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    stdout = stdout or sys.stdout
    args = build_parser().parse_args(argv)

    if not args.cmd:
        build_parser().print_help(stdout)
        return EXIT_OK

    try:
        if args.cmd == "whoami":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            try:
                user = clockify.get_user(creds["api_key"])
            except ValueError:
                _emit({"error": "INVALID_KEY"}, stdout)
                return EXIT_INVALID_KEY
            config.save_credentials(
                api_key=creds["api_key"], ics_url=creds.get("ics_url"),
                workspace_id=user["workspace_id"], user_id=user["id"],
            )
            _emit({"name": user["name"], "email": user["email"],
                   "workspace_id": user["workspace_id"]}, stdout)
            return EXIT_OK

        if args.cmd == "business-days":
            from datetime import date
            dias = pure.business_days(date.fromisoformat(args.start), date.fromisoformat(args.end))
            _emit({"days": [d.isoformat() for d in dias]}, stdout)
            return EXIT_OK

        if args.cmd == "entries":
            from datetime import date
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("America/Sao_Paulo")
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, uid = acct
            if args.date:
                win_start, win_end = pure.day_window_utc(date.fromisoformat(args.date), tz)
            else:
                win_start, win_end = pure.range_window_utc(
                    date.fromisoformat(args.start), date.fromisoformat(args.end), tz)
            out = clockify.entries(creds["api_key"], ws, uid, win_start, win_end)
            _emit({"entries": out}, stdout)
            return EXIT_OK

        if args.cmd == "resolve":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, _uid = acct
            out = resolve_mod.resolve_activity(
                creds["api_key"], ws, name=args.name, project=args.project, tag=args.tag)
            _emit(out, stdout)
            return EXIT_OK

        if args.cmd == "add":
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            raw = sys.stdin.read() if args.json == "-" else open(args.json, encoding="utf-8").read()
            try:
                items = json.loads(raw)
            except json.JSONDecodeError:
                _emit({"error": "INVALID_ITEMS", "reason": "json_malformado"}, stdout)
                return EXIT_UNKNOWN
            if not isinstance(items, list):
                _emit({"error": "INVALID_ITEMS", "reason": "esperava_lista"}, stdout)
                return EXIT_UNKNOWN
            bad = [i for i, it in enumerate(items)
                   if not isinstance(it, dict) or not _REQUIRED_ITEM_KEYS <= set(it)]
            if bad:
                _emit({"error": "INVALID_ITEMS", "missing_at": bad}, stdout)
                return EXIT_UNKNOWN
            if args.dry_run:
                _emit({"dry_run": True, "items": items}, stdout)
                return EXIT_OK
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, uid = acct
            out = resolve_mod.add_entries(creds["api_key"], ws, uid, items)
            _emit(out, stdout)
            return EXIT_OK

        if args.cmd == "prefs":
            if args.prefs_cmd == "get":
                _emit(prefs_mod.get_prefs(), stdout)
            elif args.prefs_cmd == "reset":
                prefs_mod.clear()
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "set-default":
                prefs_mod.set_default(project=args.project, task=args.task, tag=args.tag,
                                      billable=args.billable, daily_target=args.daily_target)
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "learn":
                prefs_mod.learn(args.match, project=args.project, task=args.task, tag=args.tag,
                                billable=args.billable)
                _emit({"ok": True}, stdout)
            elif args.prefs_cmd == "forget":
                _emit({"ok": True, "removed": prefs_mod.forget_learned(args.match)}, stdout)
            else:
                _emit({"error": "UNKNOWN_COMMAND", "cmd": "prefs"}, stdout)
                return EXIT_UNKNOWN
            return EXIT_OK

        _emit({"error": "UNKNOWN_COMMAND", "cmd": args.cmd}, stdout)
        return EXIT_UNKNOWN

    except http_json.HttpError as e:
        _emit({"error": "HTTP_ERROR", "status": e.status}, stdout)
        return EXIT_HTTP
```

> Notas:
> - **billable** usa `BooleanOptionalAction` → `--billable`/`--no-billable`/ausente = `True`/`False`/`None`. `None` ("não mexer") é descartado pelo `_clean` do prefs; `False` (faturável=não) agora é representável (era impossível com `store_true`).
> - **Cache de conta:** `entries`/`add`/`resolve` leem `workspace_id`+`user_id` do `credentials.json` via `_account` e **só** chamam `get_user` se o cache estiver incompleto — o que não ocorre após um `whoami` bem-sucedido. Isso elimina a rede no caminho quente e torna os testes determinísticos (sem I/O real). Se o `_account` precisar resolver e a chave for inválida, ele emite `INVALID_KEY` e o chamador retorna `EXIT_INVALID_KEY` (nunca traceback).
> - **Validação de items (`add`):** rejeita JSON malformado, `items` que não seja lista, e items sem as chaves obrigatórias (`date/start/end/task`) com `INVALID_ITEMS` — antes de qualquer escrita.
> - Onboarding (gravar a chave) NÃO é subcomando do CLI — quem grava `credentials.json` é a skill (escreve o arquivo via ferramenta de arquivo) e valida via `whoami`; ver Task 9.

- [ ] **Step 4: Rodar — deve passar**

Run: `cd clockify-cowork/scripts && python3 -m pytest tests/test_cli.py -q`
Expected: PASS (11 testes).

- [ ] **Step 5: Rodar a suíte inteira**

Run: `cd clockify-cowork/scripts && python3 -m pytest -q`
Expected: PASS (todos os módulos).

- [ ] **Step 6: Commit**

```bash
git add clockify-cowork/scripts/clockify_cli/cli.py clockify-cowork/scripts/tests/test_cli.py
git commit -m "feat(cli): subcomandos (whoami/entries/resolve/add/prefs) + testes"
```

---

## Task 9: Skill conversacional (`SKILL.md`)

**Files:**
- Create: `clockify-cowork/skills/clockify-tracking/SKILL.md`

A skill é a adaptação de `commands/clockify-tracking.md` (que chama tools MCP) para chamar o **CLI**. Mantém TODA a disciplina conversacional (i18n, leigo, precedência aprendida→padrão→perguntar, W-1 sempre com project, dry-run, anti-duplicata, gestão de prefs) — só troca o mecanismo.

- [ ] **Step 1: Definir a convenção de invocação no topo da skill**

Usar o caminho decidido no **Task 0**:
- Invocação A: `RUN="python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli"`
- Invocação B (fallback): na 1ª execução, `cp -r ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli .clockify/bin/` e `RUN="python3 .clockify/bin/clockify_cli"`.

- [ ] **Step 2: Escrever `SKILL.md`** (frontmatter + corpo)

```markdown
---
name: clockify-tracking
description: Lança horas no Clockify conversando na língua da pessoa (um dia ou um período), lendo credencial e preferências de arquivos locais na pasta do projeto.
---

Você lança as horas de alguém no Clockify, de forma colaborativa. **Converse SEMPRE no
idioma da pessoa.** O trabalho de IO é feito por um **CLI local** que devolve **JSON**;
**você** fala com a pessoa. **A pessoa é leiga: nunca mostre JSON, IDs, nomes de campo,
flags nem jargão.**

## Antes de tudo — a pessoa PRECISA estar num projeto (pasta local)

A configuração (chave + preferências) é guardada numa pasta `.clockify/` DENTRO da pasta do
projeto. Isso só persiste se a pessoa estiver trabalhando num **projeto com pasta local** —
**sem projeto, a config cai num ambiente temporário que some entre sessões** e ela teria que
recolar a chave toda vez. Então este é o PRIMEIRO passo, antes de conectar:

1. Rode `pwd`. Se o caminho for um lugar temporário (ex.: começa com `/sessions/` e **não**
   contém `/mnt/`), ou se `CLAUDE_PROJECT_DIR` estiver vazio, a pessoa NÃO está num projeto.
2. Se NÃO houver projeto, oriente em linguagem leiga e **pare** até existir:
   *"Pra eu lembrar da sua conexão de uma conversa pra outra, você precisa estar dentro de um
   projeto (uma pasta sua). Lá em cima, clique em **'Trabalhar em um projeto'** e **crie ou
   escolha uma pasta** — pode ser uma pasta nova chamada 'Clockify'. Depois me chame de novo."*
3. Se o caminho for uma pasta de projeto (contém `/mnt/` ou parece `/Users/...`), siga.

(Os caminhos exatos do sinal são confirmados no Passo 0 do plano; ajuste a heurística ao que
o Task 0 observar. `CLAUDE_PROJECT_DIR` definido é um bom indicador de que há projeto.)

## Como rodar o CLI

Rode no terminal: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli <subcomando> [args]`.
Cada comando imprime UMA linha JSON.

**Fallback (se o terminal não alcançar o plugin):** se esse comando falhar com algo como
"No such file or directory", o terminal do sandbox não está montando a pasta do plugin.
Faça UMA vez, com as **ferramentas de arquivo** (que enxergam os caminhos reais do Mac
mesmo quando o terminal não os monta): use Glob/Read para ler todos os `.py` de
`${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli/` e use Write para recriá-los em
`.clockify/bin/clockify_cli/` na pasta do projeto; depois rode
`python3 .clockify/bin/clockify_cli <subcomando>`. (NÃO dependa de `cp` no terminal — se o
terminal não vê o plugin, `cp` também não veria.)

## Conexão (1ª vez ou chave trocada)

1. Rode `... whoami`.
2. Se vier `{"error":"NO_KEY"}`: peça a chave em linguagem leiga — *"Pra começar, cola
   aqui sua chave do Clockify (pego em https://app.clockify.me/user/settings → aba
   Advanced → Generate)."* Quando a pessoa colar:
   a. **Proteja a credencial ANTES de gravá-la.** Olhe o `.gitignore` da raiz do projeto
      (ferramenta de arquivo): se existir e NÃO contiver uma linha `.clockify/`, acrescente
      `.clockify/`; se não existir `.gitignore`, crie um contendo `.clockify/`. (Isso evita
      que a chave de texto puro seja commitada no repo da PESSOA — é a proteção que importa.)
   b. **Grave** `.clockify/credentials.json` com
      `{"api_key":"<a chave>","ics_url":null,"workspace_id":null,"user_id":null}` (Write).
   c. Rode `... whoami` de novo.
3. Se vier `{"error":"INVALID_KEY"}`: *"Essa chave não funcionou, confere e tenta de novo."*
4. Se vier `{"error":"HTTP_ERROR",...}` (ou o comando falhar por rede): diga, leigo, que o
   Clockify não respondeu agora e ofereça tentar de novo em instantes. **Não** trate como
   chave inválida nem peça a chave de novo.
5. Sucesso (`{"name":...}`): cumprimente com o nome da conta. `workspace_id` e `user_id`
   já ficam em cache (o caminho de lançamento não chama a rede de novo à toa).

Leia as preferências UMA vez: `... prefs get` → guarde `default` (pode ser `{}`) e a lista
`learned` (cada item tem `match` e `project`, às vezes `task`/`tag`/`billable`).

## Passo 0 — Um dia ou um período?

Pergunte em linguagem simples: **"Quer lançar as horas de hoje / de um dia, ou de um
período (vários dias)?"**. Um passo de cada vez.

## A) Um dia

1. **Anti-duplicata:** `... entries --date AAAA-MM-DD`. Se `entries` não estiver vazio,
   avise o que já existe (sem jargão) e pergunte se continua.
2. **(Sem ICS nesta versão)** a pessoa dita as atividades com início e fim.
3. **Reconhecer cada atividade — por PRECEDÊNCIA:** (1) **aprendida** (match igual/contém →
   usa o `project` dela), (2) **padrão** (propõe a `default`), (3) **perguntar** o
   cliente/projeto. **Validar com** `... resolve --name "<tarefa>" --project "<projeto>"`
   (SEMPRE com `--project`; sem ele volta "projeto necessário"). Status:
   `OK` → resolvido; `AMBIGUO` → mostre os nomes dos `candidatos` e peça para escolher;
   `NAO_ENCONTRADO` → diga simples e pergunte o nome certo.
4. **Conferir:** mostre uma tabela limpa (atividade · cliente/projeto · duração) + total.
   Aceite ajustes.
5. **Gravar:** monte a lista de items `[{description, date "AAAA-MM-DD", start "HH:MM",
   end "HH:MM", task, project, tag?, billable?}]`. Rode primeiro
   `echo '<json>' | ... add --json - --dry-run` e confira; **só depois do "pode lançar"**,
   `echo '<json>' | ... add --json -`. Pela resposta: conte `gravados` de `total`; se
   `pulados_duplicata` > 0, avise que itens iguais já existiam e foram pulados; se
   `falhou_em` vier preenchido, explique simples (use `motivo`) e ofereça repetir só o resto.

## B) Um período (vários dias)

1. **Dias úteis:** `... business-days --start AAAA-MM-DD --end AAAA-MM-DD` → apresente `days`.
2. **Podar exceções** (feriados/férias) conversando.
3. **Anti-duplicata:** `... entries --start --end`; avise dias que já têm lançamento.
4. **Reconhecer atividades dia a dia** pela MESMA precedência do A.3 (a pessoa dita; valide
   com `resolve` sempre passando `--project`). Atalho: "mesma coisa nos próximos dias".
5. **Conferir** tabela por dia + total. Em lotes grandes, confirme totais antes.
6. **Gravar:** um único `add --json -` com TODOS os items de TODOS os dias (dry-run primeiro).
   Reporte como no A.5.

## Aprender um padrão (opcional, com consentimento)

Se uma palavra aparece sempre ligada ao mesmo destino, pergunte UMA vez: *"Toda vez que
aparecer 'X', já lanço em <projeto>?"*. Só com o "sim":
`... prefs learn --match "X" --project "<projeto>" [--task ...] [--tag ...] [--billable]`.

## Gerenciar o que eu sei

- **"O que você sabe sobre mim?"** → `... prefs get` e conte em linguagem natural.
- **Esquecer uma coisa** → confirme a palavra-chave e `... prefs forget --match "X"`; pela
  resposta, `removed:true` confirma, `false` diz que não havia nada.
- **Recomeçar do zero** (zerar atividade padrão + aprendizados, mantendo a conexão) →
  confirme que é irreversível e, **só após o "sim"**, rode `... prefs reset`. Confirme que
  recomeçou limpo.
- **Desconectar / apagar a chave** → confirme que isso remove a conexão deste projeto e é
  irreversível e, **só após o "sim"**, apague `.clockify/credentials.json` com a ferramenta
  de arquivo. Os aprendizados em `.clockify/prefs.json` permanecem — a não ser que a pessoa
  também peça "recomeçar do zero".

**Regras de ouro:** nunca grave sem conferir (dry-run antes); nunca apague sem confirmar;
nunca mostre JSON/IDs/jargão; fale na língua da pessoa; ao resolver, sempre passe `--project`.
```

- [ ] **Step 3: Commit**

```bash
git add clockify-cowork/skills/clockify-tracking/SKILL.md
git commit -m "feat(skill): clockify-tracking conversacional sobre o CLI local"
```

---

## Task 10: Atualizar commands, plugin.json e .gitignore; remover connector remoto

**Files:**
- Modify: `clockify-cowork/.claude-plugin/plugin.json`
- Delete: `clockify-cowork/.mcp.json`
- Modify: `clockify-cowork/commands/clockify-tracking.md`
- Modify: `clockify-cowork/commands/clockify.md`
- Modify: `.gitignore`

- [ ] **Step 1: `plugin.json` — remover `mcpServers`, bump versão, declarar skills**

```json
{
  "name": "clockify-cowork",
  "version": "1.0.0",
  "description": "Lança horas no Clockify pelo Cowork via skill + CLI local (sem servidor).",
  "author": { "name": "AI Product Innovation · PG" },
  "keywords": ["clockify", "time-tracking", "cowork"],
  "commands": ["./commands/"],
  "skills": ["./skills/"]
}
```

- [ ] **Step 2: Remover o connector remoto**

```bash
git rm clockify-cowork/.mcp.json
```

- [ ] **Step 3: `commands/clockify-tracking.md` — virar um disparador fino da skill**

Substituir o corpo por um command curto que invoca a skill (a lógica detalhada vive na skill):

```markdown
---
description: Lança horas no Clockify conversando na língua da pessoa (um dia ou um período)
---

Use a skill **clockify-tracking** para conduzir o lançamento de horas no Clockify
(conexão na 1ª vez, um dia ou um período, sempre com dry-run e anti-duplicata, na língua
da pessoa). Siga a skill passo a passo.
```

- [ ] **Step 4: `commands/clockify.md` — virar "status / está tudo certo?"**

```markdown
---
description: Confere a conexão com o Clockify e mostra o que está configurado
---

**Passo 1 — projeto (pasta local).** Antes de tudo, confirme que a pessoa está num projeto:
rode `pwd`; se for um lugar temporário (`/sessions/...` sem `/mnt/`) ou `CLAUDE_PROJECT_DIR`
estiver vazio, oriente a pessoa, em linguagem leiga, a clicar em **"Trabalhar em um projeto"**
e criar/escolher uma pasta (a config não persiste sem isso) — e **pare** até existir. (Mesma
verificação da skill `clockify-tracking`.)

**Passo 2 — conexão.** Com projeto confirmado, rode
`python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli whoami`.
- `{"error":"NO_KEY"}` → use a skill **clockify-tracking** para conectar (peça a chave e
  grave `.clockify/credentials.json`).
- `{"error":"INVALID_KEY"}` → avise, em linguagem leiga, que a chave não funcionou.
- `{"error":"HTTP_ERROR",...}` → diga que o Clockify não respondeu agora; ofereça tentar de novo.
- Sucesso → confirme a conta conectada (use o `name`). Em seguida rode
  `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli prefs get` e conte, em linguagem
  natural, se há atividade padrão e quantas atividades aprendidas existem. **Nunca mostre
  JSON/IDs.**
```

- [ ] **Step 5: `.gitignore` do REPO — higiene de teste local (NÃO é a proteção do usuário)**

Adicionar a linha `.clockify/` ao `.gitignore` da raiz **deste repo**. ATENÇÃO: isto cobre
apenas a pasta que pode surgir AQUI durante testes locais. **NÃO** protege a pasta do
usuário final (que roda o plugin noutro projeto/repo). A proteção real da chave do usuário
é feita pela **skill** (Task 9, passo de conexão 2a), que garante `.clockify/` no
`.gitignore` da pasta DELE antes de gravar a credencial.

- [ ] **Step 6: Verificar**

Run: `cat clockify-cowork/.claude-plugin/plugin.json && test ! -f clockify-cowork/.mcp.json && echo "mcp.json removido" && grep -qx ".clockify/" .gitignore && echo "gitignore-repo ok"`
Expected: JSON sem `mcpServers` (com `skills`); "mcp.json removido"; "gitignore-repo ok".

- [ ] **Step 7: Commit**

```bash
git add clockify-cowork/.claude-plugin/plugin.json clockify-cowork/commands/clockify-tracking.md clockify-cowork/commands/clockify.md .gitignore
git commit -m "feat(plugin): remover connector remoto; commands apontam pra skill + CLI local"
```

---

## Task 11: Limpeza — remover arquitetura remota e atualizar docs

**Files:**
- Delete: `server/` (inteiro)
- Delete: `plugins/clockify-plugin/` (CLI antiga)
- Modify: `README.md`, `CLAUDE.md`, `MAINTAINER.md`, `.env`/`.env.example`/`.envrc` (se referenciam o server)

> Fazer SÓ depois do Task 9 verde e do smoke (Task 12) idealmente — `pure.py`/lógica já foram copiados. Se preferir conservador, **arquivar** em vez de apagar (mover para `docs/superpowers/_archive/`).

- [ ] **Step 1: Conferir que nada do novo CLI importa de `server/` e reconhecer o tree sujo**

Run: `grep -rn "clockify_mcp\|server/src" clockify-cowork/ || echo "sem referências ao server"`
Expected: "sem referências ao server".

NOTA (working tree): pode haver modificações NÃO-commitadas em `server/` (trabalho da
arquitetura remota, agora abandonada — ver spec §1). Elas serão **descartadas
intencionalmente** junto com o diretório no Step 2 (por isso `git rm -rf`). Se quiser
preservar o histórico desse trabalho antes de apagar, faça
`git add -A && git commit -m "chore: checkpoint da arquitetura remota antes de remover"`
ANTES do Step 2. Não há config pytest na raiz (só em `server/` e `plugins/clockify-plugin/`),
então remover `server/` não quebra coleta de testes na raiz.

- [ ] **Step 2: Remover server e CLI antiga** (`-f` porque o tree pode ter modificações)

```bash
git rm -rf server plugins/clockify-plugin
```

- [ ] **Step 3: Atualizar `CLAUDE.md`** (seção Arquitetura) para refletir: plugin Cowork = skill + CLI zero-dep local; config em `.clockify/`; sem VPS/OAuth/MCP remoto. Remover menções a `server/`, FastMCP, OAuth.

- [ ] **Step 4: Atualizar `README.md` e `MAINTAINER.md`** — instalação via marketplace no Cowork, onboarding (colar a chave), `.clockify/` por pasta, sem deploy de servidor. Remover runbook de VPS/Traefik. **NÃO tocar** `.envrc` (fluxo de publicação pela 2ª conta com `GH_TOKEN` — deve continuar funcionando). Se `.env`/`.env.example` referenciarem secrets do server (PUBLIC_URL, JWT_SECRET, CLOCKIFY_TOKEN_KEY, PREFS_DB), atualizar/remover só essas linhas no `.env.example`; o `.env` raiz é gitignored.

- [ ] **Step 5: Rodar a suíte e o grep final**

Run: `cd clockify-cowork/scripts && python3 -m pytest -q && cd ../.. && grep -rn "srv1625247\|FastMCP\|OAuth\|clockify_mcp" README.md CLAUDE.md MAINTAINER.md .env.example || echo "docs limpos"`
Expected: testes PASS; "docs limpos" (ou só menções históricas intencionais). NÃO editar `.envrc` (publicação).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remover MCP remoto/OAuth/VPS; docs para arquitetura local"
```

---

## Task 12: Smoke manual no Cowork (e2e)

Não é TDD — validação ponta a ponta no ambiente real.

- [ ] **Step 1: Publicar/atualizar o plugin** no marketplace e adicionar/atualizar no Cowork.
- [ ] **Step 2:** Em um projeto, rodar `/clockify` → confirmar o onboarding (colar a chave) → `whoami` retorna a conta real; `.clockify/credentials.json` criado na pasta.
- [ ] **Step 3:** Fechar e reabrir a sessão → rodar `/clockify` de novo → **não** pede a chave (persistiu).
- [ ] **Step 4:** `/clockify-tracking` para **um dia**: ditar 1–2 atividades → dry-run mostra a tabela → confirmar → `add` grava na conta real → conferir no Clockify.
- [ ] **Step 5:** Repetir o mesmo dia → confirmar que **pula por duplicata** (`pulados_duplicata` > 0, nada duplicado no Clockify).
- [ ] **Step 6:** Decommission da VPS (separado, manual): parar/remover a stack `clockify-mcp` em `/docker/clockify-mcp/` **sem tocar** `/docker/traefik/` nem outras stacks. Confirmar que as outras stacks seguem no ar.

---

## Self-Review (preenchido pelo autor do plano)

- **Cobertura do spec:** §3 arquitetura → Tasks 1–10; §4 config/onboarding → Tasks 3,9; §5 comandos/skill → Tasks 8,9,10; §6 CLI/reuso → Tasks 2,5,6,7; §7 execução no sandbox → Task 0,9; §8 segurança (gitignore) → Task 10; §9 limpeza → Task 11; §11 testing → testes em cada task; §12 ICS fora de escopo → não há task de ICS (correto). ✅
- **Placeholders:** sem TBD/TODO; todo passo de código tem código. O único ponto "decidido em runtime" (caminho de invocação) é o Task 0, que é um gate explícito, não um placeholder. ✅
- **Consistência de tipos/nomes:** `request_json(method,url,*,api_key,params,body,timeout)` usado igual em http_json/clockify/testes; `resolve_activity`/`add_entries` com as mesmas assinaturas em resolve.py e cli.py; `config.save_credentials(*,api_key,ics_url,workspace_id,user_id)` consistente com o cache de conta lido por `entries`/`add`/`resolve` (via `_account`); `prefs.get_prefs()/set_default()/learn()/forget_learned()/clear()` TODOS exercidos via CLI (`prefs get|set-default|learn|forget|reset` — `reset`→`clear()`). ✅
- **Pós-revisão (plan-critic, 2026-06-08):** corrigidos **C1** (normalização `match` em `prefs._norm`, paridade com o servidor, + teste de case/espaço), **C2** (cache `workspace_id`+`user_id` em `credentials.json`; `_account` evita `get_user` no caminho quente; testes determinísticos sem rede), **W1** (`billable` via `BooleanOptionalAction` → `False` representável), **W2** (`.gitignore` real na pasta do usuário via skill; o do repo é só higiene de teste), **W3** (`git rm -rf` + nota de descarte intencional do tree sujo), **W4** (fallback por file tools, sem circularidade de `cp`), **W5** (401/403→inválida + ramo `HTTP_ERROR` na skill). NOTAs N1/N3/N4 endereçadas; N2 (`default: {}` vs `None`) mantido intencional (skill trata `{}`). ✅
```
