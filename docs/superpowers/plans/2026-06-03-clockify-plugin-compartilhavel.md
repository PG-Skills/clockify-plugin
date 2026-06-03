# Clockify Plugin Compartilhável — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o `clockify-horas` num plugin do Claude Code, distribuível por marketplace privado, sem nenhum dado pessoal do autor, com onboarding guiado (`/clockify-setup`) e config por-usuário em `~/.config/clockify-horas/config.json`.

**Architecture:** Mantém a separação cérebro/IO. A CLI ganha um subcomando `config` que faz todo o I/O determinístico da config (set/show/path/add-override/doctor); a config sai do diretório do projeto e passa a viver no dir do usuário (XDG), com precedência de variável de ambiente preservada para os testes. Os slash commands e a nova skill de setup orquestram a conversa e delegam I/O à CLI. O empacotamento como plugin inclui um SessionStart hook que autoinstala a CLI via `uv tool install`.

**Tech Stack:** Python 3.12, argparse, httpx, pytest + respx, `uv`. Claude Code plugin (`.claude-plugin/plugin.json`, `marketplace.json`, `skills/`, `commands/`, `hooks/`).

**Spec:** `docs/superpowers/specs/2026-06-03-clockify-plugin-compartilhavel-design.md`

---

## File Structure

**Criar:**
- `skills/clockify-setup/SKILL.md` — onboarding guiado
- `commands/horas.md` — `/horas` generalizado (movido de `.claude/commands/`)
- `commands/lancar.md` — `/lancar` generalizado (movido de `.claude/commands/`)
- `.claude-plugin/plugin.json` — manifesto do plugin
- `.claude-plugin/marketplace.json` — marketplace de 1 item (este repo)
- `hooks/hooks.json` — SessionStart hook
- `scripts/ensure_cli.py` — bootstrap cross-platform da CLI (guard de versão), via `uv run --script`
- `MAINTAINER.md` — como cortar release
- `tests/test_config_subcommand.py` — testes do subcomando `config`

**Modificar:**
- `src/clockify_horas/config.py` — relocação para XDG, precedência env, ICS opcional, `Override`, `load_overrides`, `read_raw`/`write_raw`, `config_path`
- `src/clockify_horas/cli.py` — subcomando `config` (path/show/set/add-override/doctor) + guard de ICS no `agenda`
- `tests/test_config.py` — isolar XDG, unificar config JSON
- `README.md` — reescrito para uso em time
- `.env.example` — vira opcional/CI (precedência env)
- `CLAUDE.md` — remover referências a `defaults.json` e overrides em auto-memória
- `.gitignore` — adicionar `.worktrees/`

**Remover:**
- `defaults.json` (dado pessoal — `git rm`)
- `.claude/commands/horas.md`, `.claude/commands/lancar.md` (movidos para `commands/`)

---

## PHASE 1 — Fundação: relocação de config + subcomando `config`

### Task 1: `config_path()`, `read_raw`/`write_raw`, dataclass `Override`

**Files:**
- Modify: `src/clockify_horas/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Adicione ao final de `tests/test_config.py`:

```python
def test_config_path_respeita_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import config_path

    assert config_path() == tmp_path / "clockify-horas" / "config.json"


def test_write_raw_cria_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    import os
    import stat

    from clockify_horas.config import config_path, read_raw, write_raw

    p = write_raw({"defaults": {"task_name": "X"}})
    assert p == config_path()
    assert read_raw() == {"defaults": {"task_name": "X"}}
    if os.name == "posix":  # chmod 600 é POSIX-only; no Windows é no-op
        assert stat.S_IMODE(p.stat().st_mode) == 0o600


def test_read_raw_ausente_retorna_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import read_raw

    assert read_raw() == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py::test_config_path_respeita_xdg tests/test_config.py::test_write_raw_cria_arquivo tests/test_config.py::test_read_raw_ausente_retorna_vazio -v`
Expected: FAIL — `ImportError: cannot import name 'config_path'`.

- [ ] **Step 3: Write minimal implementation**

No topo de `src/clockify_horas/config.py`, adicione `Override` junto às dataclasses e as funções de path/IO:

```python
import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = "clockify-horas"


@dataclass
class Config:
    api_key: str
    workspace_id: str
    ics_url: str


@dataclass
class Defaults:
    task_name: str
    tag_name: str
    billable: bool
    daily_target_hours: float


@dataclass
class Override:
    match: str
    task_name: str
    tag_name: str
    billable: bool


def config_path() -> Path:
    """Local da config por SO. ``$XDG_CONFIG_HOME`` tem prioridade em qualquer SO
    (usado para isolar testes); no Windows usa ``%APPDATA%``; senão ``~/.config``.
    """
    base = os.getenv("XDG_CONFIG_HOME")
    if base:
        root = Path(base)
    elif os.name == "nt" and os.getenv("APPDATA"):
        root = Path(os.environ["APPDATA"])
    else:
        root = Path.home() / ".config"
    return root / APP_DIR / "config.json"


def read_raw(path: Path | None = None) -> dict:
    p = path or config_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def write_raw(data: dict, path: Path | None = None) -> Path:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if os.name == "posix":  # chmod 600 é POSIX-only
        p.chmod(0o600)
    return p
```

(Mantenha os imports já existentes; remova duplicatas se houver.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: os 3 novos testes PASS (os antigos podem quebrar — corrigidos na Task 2).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/config.py tests/test_config.py
git commit -m "feat(config): config_path XDG + read_raw/write_raw + Override"
```

---

### Task 2: `load_config` com precedência env + ICS opcional

**Files:**
- Modify: `src/clockify_horas/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Substitua os testes `test_load_config_le_variaveis` e `test_load_config_falta_chave_levanta` em `tests/test_config.py` por versões isoladas via XDG, e adicione os casos de arquivo e ICS-opcional:

```python
def test_load_config_env_tem_precedencia(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "key123"
    assert cfg.workspace_id == "ws1"
    assert cfg.ics_url == "https://x/cal.ics"


def test_load_config_le_do_arquivo(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    from clockify_horas.config import write_raw

    write_raw(
        {
            "clockify": {"api_key": "fileKey", "workspace_id": "fileWs"},
            "outlook": {"ics_url": "https://file/cal.ics"},
        }
    )
    cfg = load_config(use_dotenv=False)
    assert cfg.api_key == "fileKey"
    assert cfg.workspace_id == "fileWs"
    assert cfg.ics_url == "https://file/cal.ics"


def test_load_config_falta_chave_levanta(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("CLOCKIFY_API_KEY", raising=False)
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    try:
        load_config(use_dotenv=False)
    except ValueError as e:
        assert "CLOCKIFY_API_KEY" in str(e)
    else:
        raise AssertionError("esperava ValueError")


def test_load_config_ics_opcional(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("OUTLOOK_ICS_URL", raising=False)
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "w")
    cfg = load_config(use_dotenv=False)
    assert cfg.ics_url == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `load_config` ainda exige `OUTLOOK_ICS_URL` (test_load_config_ics_opcional quebra) e ainda usa o `_REQUIRED` antigo.

- [ ] **Step 3: Write minimal implementation**

Em `src/clockify_horas/config.py`, substitua a função `load_config` (e remova a constante `_REQUIRED`):

```python
def load_config(use_dotenv: bool = True, path: Path | None = None) -> Config:
    """Carrega credenciais. Precedência: variável de ambiente > arquivo de config.

    ICS é opcional (só usado pelo subcomando ``agenda``). ``use_dotenv=False`` pula a
    leitura do .env nos testes.
    """
    if use_dotenv:
        load_dotenv()
    data = read_raw(path)
    ck = data.get("clockify", {})
    ol = data.get("outlook", {})
    api_key = os.getenv("CLOCKIFY_API_KEY") or ck.get("api_key", "")
    workspace_id = os.getenv("CLOCKIFY_WORKSPACE_ID") or ck.get("workspace_id", "")
    ics_url = os.getenv("OUTLOOK_ICS_URL") or ol.get("ics_url", "")
    missing = [
        name
        for name, val in (
            ("CLOCKIFY_API_KEY", api_key),
            ("CLOCKIFY_WORKSPACE_ID", workspace_id),
        )
        if not val
    ]
    if missing:
        raise ValueError(
            f"Configuração faltando: {', '.join(missing)}. Rode /clockify-setup."
        )
    return Config(api_key=api_key, workspace_id=workspace_id, ics_url=ics_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/config.py tests/test_config.py
git commit -m "feat(config): precedência env>arquivo e ICS opcional em load_config"
```

---

### Task 3: `load_defaults` + `load_overrides` no config unificado

**Files:**
- Modify: `src/clockify_horas/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

Substitua `test_load_defaults_le_json` em `tests/test_config.py` e adicione overrides:

```python
def test_load_defaults_do_config(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import write_raw

    write_raw(
        {
            "defaults": {
                "task_name": "Time IA",
                "tag_name": "Atividades Internas",
                "billable": False,
                "daily_target_hours": 8.0,
            }
        }
    )
    d = load_defaults()
    assert d == Defaults(
        task_name="Time IA",
        tag_name="Atividades Internas",
        billable=False,
        daily_target_hours=8.0,
    )


def test_load_defaults_incompleto_levanta(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import write_raw

    write_raw({"defaults": {"task_name": "Só isso"}})
    try:
        load_defaults()
    except ValueError:
        pass
    else:
        raise AssertionError("esperava ValueError")


def test_load_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import Override, load_overrides, write_raw

    write_raw(
        {
            "overrides": [
                {
                    "match": "San Pablo",
                    "task_name": "Assinatura",
                    "tag_name": "Implantação",
                    "billable": True,
                }
            ]
        }
    )
    assert load_overrides() == [
        Override(
            match="San Pablo",
            task_name="Assinatura",
            tag_name="Implantação",
            billable=True,
        )
    ]


def test_load_overrides_vazio(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from clockify_horas.config import load_overrides, write_raw

    write_raw({})
    assert load_overrides() == []
```

Atualize o import do topo do arquivo de teste para:

```python
from clockify_horas.config import Defaults, load_config, load_defaults
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `load_defaults` ainda recebe `path` de `defaults.json` e `load_overrides` não existe.

- [ ] **Step 3: Write minimal implementation**

Em `src/clockify_horas/config.py`, substitua `load_defaults` e adicione `load_overrides`:

```python
def load_defaults(path: Path | None = None) -> Defaults:
    d = read_raw(path).get("defaults", {})
    try:
        return Defaults(
            task_name=d["task_name"],
            tag_name=d["tag_name"],
            billable=bool(d["billable"]),
            daily_target_hours=float(d["daily_target_hours"]),
        )
    except KeyError as e:
        raise ValueError(f"defaults incompletos no config ({e}). Rode /clockify-setup.") from e


def load_overrides(path: Path | None = None) -> list[Override]:
    raw = read_raw(path).get("overrides", [])
    return [
        Override(
            match=o["match"],
            task_name=o["task_name"],
            tag_name=o["tag_name"],
            billable=bool(o["billable"]),
        )
        for o in raw
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/config.py tests/test_config.py
git commit -m "feat(config): load_defaults+load_overrides do config unificado"
```

---

### Task 4: subcomando `config set` + wiring no parser

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_config_subcommand.py` (criar)

- [ ] **Step 1: Write the failing test**

Crie `tests/test_config_subcommand.py`:

```python
import json

from clockify_horas.cli import main
from clockify_horas.config import config_path


def test_config_set_cria_e_atualiza(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(
        [
            "config",
            "set",
            "--api-key",
            "K",
            "--workspace-id",
            "W",
            "--ics-url",
            "https://x/cal.ics",
            "--task",
            "Time IA",
            "--tag",
            "Célula de Inovação",
            "--no-billable",
            "--daily-target",
            "8",
        ]
    )
    assert rc == 0
    data = json.loads(config_path().read_text(encoding="utf-8"))
    assert data["clockify"] == {"api_key": "K", "workspace_id": "W"}
    assert data["outlook"] == {"ics_url": "https://x/cal.ics"}
    assert data["defaults"] == {
        "task_name": "Time IA",
        "tag_name": "Célula de Inovação",
        "billable": False,
        "daily_target_hours": 8.0,
    }

    rc = main(["config", "set", "--task", "Outra Tarefa"])
    assert rc == 0
    data = json.loads(config_path().read_text(encoding="utf-8"))
    assert data["defaults"]["task_name"] == "Outra Tarefa"
    assert data["clockify"]["api_key"] == "K"  # preservado
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_subcommand.py -v`
Expected: FAIL — argparse erro "invalid choice: 'config'".

- [ ] **Step 3: Write minimal implementation**

Em `src/clockify_horas/cli.py`, adicione os imports e as funções do subcomando. No topo, estenda o import de config:

```python
from clockify_horas.config import (
    config_path,
    load_config,
    load_defaults,
    load_overrides,
    read_raw,
    write_raw,
)
```

Adicione as funções (antes de `build_parser`):

```python
def _cmd_config_set(args: argparse.Namespace) -> int:
    data = read_raw()
    ck = data.setdefault("clockify", {})
    ol = data.setdefault("outlook", {})
    df = data.setdefault("defaults", {})
    data.setdefault("overrides", [])
    if args.api_key is not None:
        ck["api_key"] = args.api_key
    if args.workspace_id is not None:
        ck["workspace_id"] = args.workspace_id
    if args.ics_url is not None:
        ol["ics_url"] = args.ics_url
    if args.task is not None:
        df["task_name"] = args.task
    if args.tag is not None:
        df["tag_name"] = args.tag
    if args.billable is not None:
        df["billable"] = args.billable
    if args.daily_target is not None:
        df["daily_target_hours"] = float(args.daily_target)
    p = write_raw(data)
    print(f"Config atualizada: {p}")
    return 0
```

Em `build_parser`, antes do `return parser`, adicione o subparser aninhado:

```python
    p_config = sub.add_parser("config", help="Gerencia a config por-usuário")
    config_sub = p_config.add_subparsers(dest="config_cmd", required=True)

    p_set = config_sub.add_parser("set", help="Define campos da config")
    p_set.add_argument("--api-key")
    p_set.add_argument("--workspace-id")
    p_set.add_argument("--ics-url")
    p_set.add_argument("--task")
    p_set.add_argument("--tag")
    p_set.add_argument("--daily-target")
    bill = p_set.add_mutually_exclusive_group()
    bill.add_argument("--billable", dest="billable", action="store_const", const=True, default=None)
    bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_set.set_defaults(func=_cmd_config_set)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_subcommand.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_config_subcommand.py
git commit -m "feat(cli): subcomando config set"
```

---

### Task 5: `config path` + `config show` (com key redigida)

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_config_subcommand.py`

- [ ] **Step 1: Write the failing test**

Adicione a `tests/test_config_subcommand.py`:

```python
def test_config_path_imprime_caminho(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(["config", "path"])
    assert rc == 0
    out = capsys.readouterr().out.strip()
    assert out == str(config_path())


def test_config_show_redige_api_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    main(["config", "set", "--api-key", "SEGREDO", "--workspace-id", "W", "--task", "T"])
    capsys.readouterr()
    rc = main(["config", "show"])
    assert rc == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["clockify"]["api_key"] == "***"
    assert shown["clockify"]["workspace_id"] == "W"
    assert shown["defaults"]["task_name"] == "T"


def test_config_show_sem_config_erro(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(["config", "show"])
    assert rc == 1
    assert "clockify-setup" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_subcommand.py -k "path_imprime or show" -v`
Expected: FAIL — "invalid choice: 'path'".

- [ ] **Step 3: Write minimal implementation**

Em `cli.py`, adicione:

```python
def _cmd_config_path(args: argparse.Namespace) -> int:
    print(str(config_path()))
    return 0


def _cmd_config_show(args: argparse.Namespace) -> int:
    data = read_raw()
    if not data:
        print("Sem config. Rode /clockify-setup.", file=sys.stderr)
        return 1
    red = json.loads(json.dumps(data))
    if red.get("clockify", {}).get("api_key"):
        red["clockify"]["api_key"] = "***"
    print(json.dumps(red, ensure_ascii=False, indent=2))
    return 0
```

Em `build_parser`, dentro do bloco `config_sub`:

```python
    p_path = config_sub.add_parser("path", help="Imprime o caminho do arquivo de config")
    p_path.set_defaults(func=_cmd_config_path)

    p_show = config_sub.add_parser("show", help="Imprime a config (api_key redigida)")
    p_show.set_defaults(func=_cmd_config_show)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_subcommand.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_config_subcommand.py
git commit -m "feat(cli): config path + config show redigido"
```

---

### Task 6: `config add-override`

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_config_subcommand.py`

- [ ] **Step 1: Write the failing test**

Adicione a `tests/test_config_subcommand.py`:

```python
def test_config_add_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(
        [
            "config",
            "add-override",
            "--match",
            "San Pablo",
            "--task",
            "Assinatura",
            "--tag",
            "Implantação",
            "--billable",
        ]
    )
    assert rc == 0
    data = json.loads(config_path().read_text(encoding="utf-8"))
    assert data["overrides"] == [
        {
            "match": "San Pablo",
            "task_name": "Assinatura",
            "tag_name": "Implantação",
            "billable": True,
        }
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_subcommand.py::test_config_add_override -v`
Expected: FAIL — "invalid choice: 'add-override'".

- [ ] **Step 3: Write minimal implementation**

Em `cli.py`:

```python
def _cmd_config_add_override(args: argparse.Namespace) -> int:
    data = read_raw()
    ov = data.setdefault("overrides", [])
    ov.append(
        {
            "match": args.match,
            "task_name": args.task,
            "tag_name": args.tag,
            "billable": bool(args.billable) if args.billable is not None else False,
        }
    )
    p = write_raw(data)
    print(f"Override adicionado ({args.match}): {p}")
    return 0
```

Em `build_parser`, dentro de `config_sub`:

```python
    p_ovr = config_sub.add_parser("add-override", help="Adiciona regra de override por cliente")
    p_ovr.add_argument("--match", required=True, help="Palavra-chave do cliente/projeto")
    p_ovr.add_argument("--task", required=True)
    p_ovr.add_argument("--tag", required=True)
    ovr_bill = p_ovr.add_mutually_exclusive_group()
    ovr_bill.add_argument(
        "--billable", dest="billable", action="store_const", const=True, default=None
    )
    ovr_bill.add_argument("--no-billable", dest="billable", action="store_const", const=False)
    p_ovr.set_defaults(func=_cmd_config_add_override)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_subcommand.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_config_subcommand.py
git commit -m "feat(cli): config add-override"
```

---

### Task 7: `config doctor` (validação real contra a API)

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_config_subcommand.py`

- [ ] **Step 1: Write the failing test**

Adicione a `tests/test_config_subcommand.py` (topo: `import httpx`, `import respx`):

```python
import httpx
import respx

BASE = "https://api.clockify.me/api/v1"


def _seed_config():
    """Config completa (defaults inclusos) para o doctor exercitar todas as ramificações."""
    main(
        [
            "config",
            "set",
            "--api-key",
            "K",
            "--workspace-id",
            "W",
            "--task",
            "T",
            "--tag",
            "G",
            "--no-billable",
            "--daily-target",
            "8",
        ]
    )


@respx.mock
def test_config_doctor_ok(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)  # sem o .env do repo no cwd (hermético)
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    _seed_config()
    respx.get(f"{BASE}/workspaces").mock(
        return_value=httpx.Response(200, json=[{"id": "W", "name": "Meu WS"}])
    )
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "U"}))
    respx.get(f"{BASE}/workspaces/W/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "P", "name": "Proj"}])
    )
    respx.get(f"{BASE}/workspaces/W/projects/P/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "TID", "name": "T"}])
    )
    respx.get(f"{BASE}/workspaces/W/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "GID", "name": "G"}])
    )
    rc = main(["config", "doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK: API key e workspace válidos." in out
    assert "OK: tarefa default 'T' existe." in out
    assert "OK: etiqueta default 'G' existe." in out


@respx.mock
def test_config_doctor_ics_ok(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    _seed_config()
    main(["config", "set", "--ics-url", "https://x/cal.ics"])
    respx.get(f"{BASE}/workspaces").mock(return_value=httpx.Response(200, json=[{"id": "W"}]))
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "U"}))
    respx.get(f"{BASE}/workspaces/W/projects").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{BASE}/workspaces/W/tags").mock(return_value=httpx.Response(200, json=[]))
    respx.head("https://x/cal.ics").mock(return_value=httpx.Response(200))
    rc = main(["config", "doctor"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "OK: link ICS acessível." in out


@respx.mock
def test_config_doctor_key_invalida(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    _seed_config()
    respx.get(f"{BASE}/workspaces").mock(return_value=httpx.Response(401))
    rc = main(["config", "doctor"])
    assert rc == 1
    assert "FAIL" in capsys.readouterr().out
```

> **C1 (plan-critic):** a hermeticidade vem de o `doctor` usar `load_config(use_dotenv=False)`
> (Step 3), que **não chama `load_dotenv()`** — então o `.env` real da raiz do repo nunca vaza.
> Importante: `load_dotenv()` faz descoberta de `.env` baseada em **frame** (sobe de
> `src/clockify_horas/` até a raiz do repo), não em cwd — por isso `monkeypatch.chdir` **não**
> protegeria; só `use_dotenv=False` protege. Os `chdir(tmp_path)` aqui são defesa extra inócua
> (o `XDG_CONFIG_HOME` já isola o arquivo), não a causa da hermeticidade.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_subcommand.py -k doctor -v`
Expected: FAIL — "invalid choice: 'doctor'".

- [ ] **Step 3: Write minimal implementation**

Em `cli.py`:

```python
def _cmd_config_doctor(args: argparse.Namespace) -> int:
    if not read_raw():
        print("FAIL: sem config. Rode /clockify-setup.")
        return 1
    try:
        # use_dotenv=False: o doctor valida o config XDG + env, sem puxar um .env de cwd.
        cfg = load_config(use_dotenv=False)
    except ValueError as e:
        print(f"FAIL: {e}")
        return 1

    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    try:
        ids = {w["id"] for w in client.list_workspaces()}
    except httpx.HTTPStatusError as e:
        print(f"FAIL: API key inválida ou sem acesso (HTTP {e.response.status_code}).")
        return 1
    if cfg.workspace_id in ids:
        print("OK: API key e workspace válidos.")
    else:
        print(f"FAIL: workspace '{cfg.workspace_id}' não está entre os seus workspaces.")
        return 1

    try:
        d = load_defaults()
        md = client.get_metadata()
        task_names = {name for (_pid, name) in md.tasks}
        if d.task_name in task_names:
            print(f"OK: tarefa default '{d.task_name}' existe.")
        else:
            print(f"WARN: tarefa default '{d.task_name}' não encontrada no workspace.")
        if d.tag_name in md.tags:
            print(f"OK: etiqueta default '{d.tag_name}' existe.")
        else:
            print(f"WARN: etiqueta default '{d.tag_name}' não encontrada.")
    except ValueError:
        print("WARN: defaults ainda não configurados.")

    if cfg.ics_url:
        try:
            httpx.head(cfg.ics_url, timeout=10.0, follow_redirects=True).raise_for_status()
            print("OK: link ICS acessível.")
        except httpx.HTTPError:
            print("WARN: link ICS não respondeu (necessário só para /horas).")
    else:
        print("WARN: ICS não configurado (necessário só para /horas).")
    return 0
```

Em `build_parser`, dentro de `config_sub`:

```python
    p_doc = config_sub.add_parser("doctor", help="Valida a config contra a API")
    p_doc.set_defaults(func=_cmd_config_doctor)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_subcommand.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_config_subcommand.py
git commit -m "feat(cli): config doctor valida key/workspace/defaults/ICS"
```

---

### Task 8: Guard de ICS ausente no `agenda`

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Adicione a `tests/test_cli.py`:

```python
def test_agenda_sem_ics_erro(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # ICS explicitamente VAZIO ("") — NÃO delenv. `_cmd_agenda` usa load_config(use_dotenv=True),
    # e o load_dotenv() faz descoberta de .env baseada em FRAME (sobe de src/clockify_horas/ até
    # a raiz do repo), repopulando a var se ela estiver AUSENTE. Com a var presente e vazia,
    # override=False não a sobrescreve → o guard de ICS dispara de forma hermética em qualquer SO.
    monkeypatch.setenv("OUTLOOK_ICS_URL", "")
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "w")
    from clockify_horas.cli import main

    rc = main(["agenda", "--date", "2026-05-01"])
    assert rc == 2
    assert "ICS" in capsys.readouterr().err
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_agenda_sem_ics_erro -v`
Expected: FAIL — hoje `_cmd_agenda` tentaria buscar o ICS vazio (e provavelmente quebraria em outro ponto).

- [ ] **Step 3: Write minimal implementation**

Em `cli.py`, no início de `_cmd_agenda`, após `cfg = load_config()`:

```python
def _cmd_agenda(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not cfg.ics_url:
        print(
            "erro: ICS não configurado. Rode /clockify-setup para o fluxo do Outlook.",
            file=sys.stderr,
        )
        return 2
    target = date.fromisoformat(args.date) if args.date else date.today()
    ...
```

(Mantenha o resto do corpo de `_cmd_agenda` igual.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + lint + types**

Run: `uv run pytest -q && uv run ruff check . && uv run pyright`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_cli.py
git commit -m "feat(cli): agenda avisa quando ICS não está configurado"
```

---

## PHASE 2 — Generalizar commands + remover dado pessoal

### Task 9: Mover e generalizar `/horas` e `/lancar`

**Files:**
- Create: `commands/horas.md`, `commands/lancar.md`
- Remove: `.claude/commands/horas.md`, `.claude/commands/lancar.md`

- [ ] **Step 1: Criar `commands/horas.md`**

```markdown
---
description: Lança horas do dia no Clockify a partir da agenda do Outlook
---

Você vai lançar as horas do dia no Clockify de forma colaborativa. O argumento opcional
`$ARGUMENTS` pode conter uma data (AAAA-MM-DD); se vazio, use hoje.

Antes de tudo, rode `clockify-horas config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Caso contrário, use os `defaults` e `overrides`
retornados como base dos lançamentos.

Siga EXATAMENTE este fluxo, um passo de cada vez, conversando em português:

1. **Ler a agenda.** Rode `clockify-horas agenda --date <data>`. Cada evento vira um
   lançamento candidato: descrição = título do evento, horários = os do evento, e aplique
   os `defaults` da config (task_name, tag_name, billable).

2. **Anti-duplicata.** Rode `clockify-horas entries --date <data>`. Se a saída não for
   vazia, JÁ existem lançamentos nessa data — AVISE, mostre o que existe, e pergunte se
   quer continuar antes de seguir.

3. **Trabalho avulso.** Pergunte o que mais a pessoa fez no dia além das reuniões, com
   descrição e horários de início/fim. Acrescente como lançamentos.

4. **Overrides + edição colaborativa.** Para cada item, se a descrição casar com o campo
   `match` de algum override da config, aplique a tarefa/etiqueta/faturável daquele
   override. Mostre a lista completa em tabela (descrição, horário, tarefa, etiqueta,
   faturável, duração). Aceite ajustes em qualquer campo. Se a pessoa citar tarefa/etiqueta
   fora dos defaults/overrides, valide contra `clockify-horas meta`; se não existir, liste
   as opções e peça correção.

5. **Total do dia.** Some as durações e informe o total. Se fugir do `daily_target_hours`
   da config além de 15min, avise (sem bloquear).

6. **Confirmação + dry-run.** Monte o JSON da lista, salve em arquivo temporário e rode
   `clockify-horas add --file <tmp> --dry-run`. Mostre os payloads. Peça confirmação
   explícita.

7. **Gravar.** Só após o "pode lançar", rode `clockify-horas add --file <tmp>` (sem
   `--dry-run`). Reporte o resumo do que foi criado.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes.
```

- [ ] **Step 2: Criar `commands/lancar.md`**

```markdown
---
description: Lança horas no Clockify em vários dias de uma vez (ex: mês retroativo)
---

Você vai lançar horas no Clockify em VÁRIOS dias de uma vez. Conduza em português, um
passo de cada vez.

Antes de tudo, rode `clockify-horas config show`. Se falhar (sem config), peça para a
pessoa rodar `/clockify-setup` e pare. Caso contrário, use `defaults` e `overrides` como base.

1. **Período.** Pergunte o intervalo (ex: "maio", "01–15/05"). Converta para AAAA-MM-DD e
   rode `clockify-horas business-days --start <ini> --end <fim>`. Apresente os dias úteis.

2. **Podar exceções.** Pergunte quais dias remover (feriados, férias, dias sem trabalho).

3. **Anti-duplicata.** Rode `clockify-horas entries --start <ini> --end <fim>`. Para cada
   dia que JÁ tem lançamento, AVISE e pergunte se pula ou soma.

4. **Ditar atividades — puxando do Outlook por dia (se ICS configurado).** Para CADA dia
   selecionado, na ordem:
   a. Rode `clockify-horas agenda --date <dia>` para puxar as reuniões. Se o comando
      avisar que não há ICS, siga só com o que a pessoa ditar.
   b. MOSTRE as reuniões como lançamentos candidatos (defaults aplicados; overrides
      aplicados quando a descrição casar com algum `match`).
   c. PERGUNTE: confirma essas reuniões? O que mais fez no dia? Algum item é de outro
      projeto/tarefa/tag/faturável?
   Atalho: a pessoa pode dizer "mesma coisa nos próximos dias" para clonar. Para itens
   fora do default, valide o nome da tarefa/etiqueta contra `clockify-horas meta`.

5. **Revisão.** Mostre uma tabela por dia (data, descrição, horário, tarefa, tag,
   faturável, duração) e o total por dia. Avise dias fora do `daily_target_hours` (sem bloquear).

6. **Dry-run.** Monte UM JSON com todos os lançamentos de todos os dias, salve em arquivo
   temporário e rode `clockify-horas add --file <tmp> --dry-run`. Mostre os payloads.
   Peça confirmação explícita.

7. **Gravar.** Só após "pode lançar", rode `clockify-horas add --file <tmp>` (sem
   `--dry-run`). Reporte o resumo por dia. Se o `add` sair com código ≠ 0 (falha parcial),
   ele informa quantos itens gravou — monte um novo JSON SÓ com os itens restantes (não
   regrave os já lançados) e rode de novo.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes. Em lotes grandes,
confirme o total de dias e de horas antes de gravar.

**Dedupe (importante):** a única proteção determinística contra duplicata é o passo 3
(`entries`) + você OMITIR do JSON os dias já lançados. Não há trava no `add`.
```

- [ ] **Step 3: Remover os antigos**

```bash
git rm .claude/commands/horas.md .claude/commands/lancar.md
```

- [ ] **Step 4: Verificar que não sobrou dado pessoal**

Run: `grep -rniE "time ia|célula de inovação|san pablo|mulesoft|farmacia|\bAMS\b" commands/ ; echo "exit: $?"`
Expected: nenhuma linha (grep retorna exit 1 = "não encontrou"). Se aparecer algo, remova.

- [ ] **Step 5: Commit**

```bash
git add commands/ .claude/commands/
git commit -m "refactor(commands): generalizar /horas e /lancar e mover para commands/"
```

---

### Task 10: Remover `defaults.json` + limpar referências

**Files:**
- Remove: `defaults.json`
- Modify: `README.md`, `.env.example`, `CLAUDE.md`, `.gitignore`

- [ ] **Step 1: Remover `defaults.json`**

```bash
git rm defaults.json
```

- [ ] **Step 2: Atualizar `.gitignore`** (adicionar worktrees conforme convenção global)

Acrescente ao final de `.gitignore`:

```
.worktrees/
```

- [ ] **Step 3: Atualizar `.env.example`** (vira caminho avançado/CI)

Substitua o conteúdo de `.env.example` por:

```
# Caminho AVANÇADO/CI. O fluxo normal é /clockify-setup, que grava em
# ~/.config/clockify-horas/config.json. Variáveis aqui têm PRECEDÊNCIA sobre o arquivo.
CLOCKIFY_API_KEY=
CLOCKIFY_WORKSPACE_ID=
OUTLOOK_ICS_URL=
```

- [ ] **Step 4: Atualizar `CLAUDE.md`** — substitua a seção "Convenções específicas (gotchas)" para remover defaults pessoais e a menção a auto-memória. Novo bloco:

```markdown
## Convenções específicas (gotchas)

- **Config por-usuário** em `~/.config/clockify-horas/config.json` (macOS/Linux) ou
  `%APPDATA%\clockify-horas\config.json` (Windows); `$XDG_CONFIG_HOME` tem prioridade.
  Variáveis de ambiente têm precedência sobre o arquivo (CI/testes). Criada/editada via
  `/clockify-setup` ou o subcomando `clockify-horas config set`.
- **Tarefa resolve por NOME, globalmente** (`build_payload._resolve_task`) — o nome precisa
  ser único entre projetos.
- **Overrides por cliente** vivem na seção `overrides` do config de cada pessoa (regra por
  palavra-chave `match`). Não há dado de cliente no repo.
- **ICS é opcional**: só o subcomando `agenda` (fluxo `/horas`) precisa dele; `/lancar`
  funciona sem.
- **Horários em UTC**: conversão de hora local (America/Sao_Paulo) em `to_utc_iso`.
- **`add` é resiliente a falha parcial**: para no 1º erro, reporta "gravou N de M", sai ≠ 0.
- **Sempre dry-run antes de gravar.** Anti-duplicata = `entries` + omitir dias já lançados.
```

- [ ] **Step 5: Atualizar `README.md`** — feito na Task 15 (reescrita completa para time). Aqui apenas garantir que `uv run clockify-horas` na seção CLI não cite `defaults.json`. Deixe a reescrita para a Task 15.

- [ ] **Step 6: Verificar suíte ainda verde** (nenhum teste depende de `defaults.json` após Task 3)

Run: `uv run pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: remover defaults.json e dados pessoais; gitignore worktrees"
```

---

## PHASE 3 — Skill de onboarding `/clockify-setup`

### Task 11: Criar `skills/clockify-setup/SKILL.md`

**Files:**
- Create: `skills/clockify-setup/SKILL.md`

- [ ] **Step 1: Criar o arquivo com o conteúdo abaixo**

```markdown
---
name: clockify-setup
description: Onboarding guiado do clockify-horas — configura credenciais Clockify, link ICS do Outlook e defaults (tarefa/etiqueta/faturável) por-usuário, com verificação final. Use na primeira vez ou para reconfigurar.
---

# Setup guiado do clockify-horas

Conduza a configuração inicial em português, **um passo de cada vez**, sempre delegando o
I/O ao subcomando `clockify-horas config`. Nunca escreva o arquivo de config diretamente.

## Pré-checagem

1. Rode `clockify-horas config path` para descobrir onde a config vai morar e mostre à pessoa.
   - Se o comando **não existir**, a CLI não foi instalada. Isso é raro (o plugin instala via
     SessionStart hook). A única dependência é o **`uv`** — **não é preciso ter Python**: o
     `uv` baixa um Python gerenciado sozinho. Cheque o `uv` (`command -v uv` no macOS/Linux,
     `Get-Command uv` no Windows). Se faltar, **ofereça instalá-lo para a pessoa (com
     consentimento)** rodando o instalador oficial do SO detectado:
     - **macOS/Linux:** `curl -LsSf https://astral.sh/uv/install.sh | sh`
     - **Windows (PowerShell):** `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
     Depois de instalar o `uv`, peça para **reabrir a sessão do Claude Code** (o SessionStart
     hook então instala a CLI — baixando o Python se necessário). Se mesmo assim o
     `clockify-horas` não estiver no PATH, rode `uv tool update-shell` e reabra o terminal.
2. Rode `clockify-horas config show`. Se já houver config, pergunte se a pessoa quer
   **reconfigurar** (sobrescreve campos) ou sair.

## Passos

1. **API key.** Explique o caminho: Clockify → canto inferior esquerdo (perfil) →
   *Preferences* → aba *Advanced* (ou *Profile Settings → API*) → *Generate*. Peça a key e
   rode `clockify-horas config set --api-key "<KEY>"`.

2. **Workspace.** Rode `clockify-horas meta`. Ele lista os workspaces e metadados.
   - Se o `meta` falhar com erro de auth, a key está errada — volte ao passo 1.
   - Se houver só **um** workspace, defina-o sozinho (sem perguntar).
   - Se houver vários, liste-os **numerados** e peça o número.
   - Grave com `clockify-horas config set --workspace-id "<ID>"`.
   - Reexecute `clockify-horas meta` se necessário para obter os metadados do workspace certo.

3. **Link ICS do Outlook.** Explique: Outlook web → *Configurações* → *Calendário* →
   *Calendários compartilhados* → *Publicar um calendário* → escolha o calendário e a
   permissão → copie o link **.ics** (ICS, não o HTML). Peça o link e rode
   `clockify-horas config set --ics-url "<URL>"`. Diga que isso é opcional para quem só usa
   `/lancar`, mas necessário para `/horas`.

4. **Defaults.** A partir da saída de `meta`, mostre as **tarefas** e **etiquetas** reais
   como listas **numeradas**. Peça:
   - tarefa padrão (número) → `--task "<nome>"`
   - etiqueta padrão (número) → `--tag "<nome>"`
   - faturável por padrão? (sim/não) → `--billable` ou `--no-billable`
   - meta diária de horas (Enter para 8) → `--daily-target <n>`
   Grave tudo numa chamada: `clockify-horas config set --task "..." --tag "..." --no-billable --daily-target 8`.

5. **Overrides de cliente (opcional, pulável).** Pergunte: "Quer pré-declarar algum cliente
   com tarefa/etiqueta/faturável diferentes do padrão? (pode pular e adicionar depois)".
   - Default: pular. Se sim, para cada cliente: peça palavra-chave (`match`), tarefa,
     etiqueta e faturável, e rode
     `clockify-horas config add-override --match "..." --task "..." --tag "..." --billable`.
   - Valide os nomes contra `meta`.

6. **Prova.** Rode `clockify-horas config doctor` e mostre o resumo. Linhas `OK` = ótimo;
   `WARN` de ICS é aceitável para quem não usa `/horas`; qualquer `FAIL` precisa ser
   corrigido (volte ao passo correspondente). Ofereça rodar `/horas <hoje>` em **dry-run**
   para a pessoa ver o fluxo sem gravar nada.

Ao final, diga que a pessoa já pode usar `/horas` (um dia via Outlook) e `/lancar`
(vários dias). Reconfigurar é só rodar `/clockify-setup` de novo.
```

- [ ] **Step 2: Verificação manual de conteúdo**

Run: `grep -niE "time ia|célula de inovação|san pablo|mulesoft|farmacia|vbjuliani" skills/clockify-setup/SKILL.md ; echo "exit $?"`
Expected: nenhuma linha (exit 1).

- [ ] **Step 3: Commit**

```bash
git add skills/clockify-setup/SKILL.md
git commit -m "feat(skill): /clockify-setup onboarding guiado"
```

---

## PHASE 4 — Empacotamento como plugin + marketplace

### Task 12: `.claude-plugin/plugin.json`

**Files:**
- Create: `.claude-plugin/plugin.json`

- [ ] **Step 1: Criar o manifesto**

```json
{
  "name": "clockify-horas",
  "version": "1.0.0",
  "description": "Lançador de horas Clockify a partir da agenda do Outlook (ICS), com onboarding guiado e config por-usuário.",
  "author": { "name": "PG Consultoria" },
  "keywords": ["clockify", "time-tracking", "outlook"],
  "skills": "./skills/",
  "commands": ["./commands/"],
  "hooks": "./hooks/hooks.json"
}
```

> Formatos dos campos (`skills` string, `commands` array, `hooks` string) vêm da referência
> oficial de plugins do Claude Code (confirmada via `claude-code-guide`). `version` aqui é a
> fonte da versão de distribuição (lida pelo hook — ver C2); o `version` do `pyproject.toml`
> é interno. Não precisam casar, mas mantenha alinhados por clareza.

- [ ] **Step 2: Validar**

Run: `claude plugin validate .`
Expected: sem erros (warnings aceitáveis). Se `claude plugin validate` não existir nesta versão, pule e valide no dogfood (Task 17). Se o `validate` reclamar do formato de `skills`/`commands`/`hooks`, ajuste conforme a mensagem (string vs array) — é o único ponto do manifesto não exercitado por teste automatizado.

- [ ] **Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat(plugin): manifesto plugin.json"
```

---

### Task 13: SessionStart hook que autoinstala a CLI

**Files:**
- Create: `hooks/hooks.json`, `scripts/ensure_cli.py`

- [ ] **Step 1: Criar `scripts/ensure_cli.py`** (bootstrap cross-platform)

```python
#!/usr/bin/env python3
"""Instala/atualiza a CLI clockify-horas com guard de versão. Roda em SessionStart.
Cross-platform (macOS/Windows/Linux). Sempre sai 0 para nunca bloquear a sessão.
Invocado via `uv run --script` — só requer `uv` no PATH.
"""
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _log(msg: str) -> None:
    print(f"clockify-horas: {msg}", file=sys.stderr)


def main() -> int:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        return 0
    data = os.environ.get("CLAUDE_PLUGIN_DATA") or str(
        Path.home() / ".cache" / "clockify-horas"
    )
    Path(data).mkdir(parents=True, exist_ok=True)
    stamp = Path(data) / "cli-version"

    # C2: versão = o campo que o mantenedor faz bump no plugin.json (fonte única).
    try:
        manifest = json.loads(
            (Path(root) / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        version = str(manifest.get("version", "0"))
    except (OSError, json.JSONDecodeError):
        version = "0"

    if shutil.which("uv") is None:
        _log("'uv' não encontrado — rode /clockify-setup para instruções de instalação.")
        return 0

    fresh = (
        stamp.exists()
        and stamp.read_text(encoding="utf-8").strip() == version
        and shutil.which("clockify-horas") is not None
    )
    if fresh:
        return 0

    try:
        subprocess.run(["uv", "tool", "install", "--force", root], check=True)
        stamp.write_text(version, encoding="utf-8")
        _log(f"CLI {version} instalada/atualizada.")
    except subprocess.CalledProcessError:
        _log("falha ao instalar a CLI — rode /clockify-setup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Criar `hooks/hooks.json`**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          { "type": "command", "command": "uv run --script \"${CLAUDE_PLUGIN_ROOT}/scripts/ensure_cli.py\"" }
        ]
      }
    ]
  }
}
```

> Cross-platform: `uv run --script` roda em macOS/Windows/Linux sem depender de bash. O
> `${CLAUDE_PLUGIN_ROOT}` é expandido pelo Claude Code (não pelo shell), então funciona tanto
> em `sh` quanto em `cmd.exe`/PowerShell. Requer apenas `uv` no PATH — **não exige Python
> pré-instalado**: tanto `uv run --script` quanto `uv tool install` baixam um Python
> gerenciado quando não há um compatível (o `requires-python` guia a versão).

- [ ] **Step 3: Smoke do bootstrap localmente** (simula as variáveis do plugin)

POSIX (macOS/Linux):
Run: `CLAUDE_PLUGIN_ROOT="$PWD" CLAUDE_PLUGIN_DATA="$(mktemp -d)" uv run --script scripts/ensure_cli.py ; clockify-horas --help | head -1`
Windows (PowerShell):
Run: `$env:CLAUDE_PLUGIN_ROOT=$PWD; $env:CLAUDE_PLUGIN_DATA=$env:TEMP; uv run --script scripts/ensure_cli.py; clockify-horas --help`
Expected: instala sem erro e `clockify-horas --help` imprime o uso. (Se já houver um `clockify-horas` no PATH de dev, o `--force` apenas reinstala.)

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json scripts/ensure_cli.py
git commit -m "feat(plugin): SessionStart hook autoinstala a CLI (bootstrap Python cross-platform)"
```

---

### Task 14: `.claude-plugin/marketplace.json`

**Files:**
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Criar o marketplace (plugin no próprio repo, source relativa `.`)**

```json
{
  "name": "pg-clockify",
  "owner": { "name": "PG Consultoria" },
  "description": "Marketplace interno — lançador de horas Clockify.",
  "plugins": [
    {
      "name": "clockify-horas",
      "source": ".",
      "description": "Lançador de horas Clockify via Outlook (ICS) com onboarding guiado."
    }
  ]
}
```

> Nota: `source: "."` aponta o plugin para a raiz do próprio repositório do marketplace
> (onde vive `.claude-plugin/plugin.json`). Confirmar no dogfood (Task 17); se a versão do
> Claude Code não aceitar `.`, mover o plugin para `plugins/clockify-horas/` e usar
> `"source": "./plugins/clockify-horas"`.
>
> **Acoplamento (plan-critic W5):** se cair no fallback `plugins/clockify-horas/`, mova
> JUNTO `pyproject.toml`, `src/`, `commands/`, `skills/`, `hooks/`, `scripts/` e
> `.claude-plugin/plugin.json` para dentro de `plugins/clockify-horas/` — porque
> `${CLAUDE_PLUGIN_ROOT}` passa a ser esse subdir, e o hook lê `$ROOT/.claude-plugin/plugin.json`
> e `uv tool install "$ROOT"` (que precisa do `pyproject.toml` em `$ROOT`). O `marketplace.json`
> permanece em `.claude-plugin/` na raiz do repo. Mantenha `tests/` na raiz (não distribuído).

- [ ] **Step 2: Commit**

```bash
git add .claude-plugin/marketplace.json
git commit -m "feat(plugin): marketplace.json (1 plugin no próprio repo)"
```

---

### Task 15: `MAINTAINER.md` + README para time

**Files:**
- Create: `MAINTAINER.md`
- Modify: `README.md`

- [ ] **Step 1: Criar `MAINTAINER.md`**

```markdown
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
```

- [ ] **Step 2: Reescrever `README.md`** para foco em time:

```markdown
# clockify-horas

Plugin do Claude Code para lançar horas no Clockify a partir da agenda do Outlook (ICS).
Cada pessoa pluga as próprias credenciais e defaults — não há dado de ninguém no repo.

## Instalação

No Claude Code:

```
/plugin marketplace add <git-url-deste-repo>
/plugin install clockify-horas@pg-clockify
/clockify-setup
```

- `/clockify-setup` configura sua API key do Clockify, o link ICS do Outlook e seus
  defaults (tarefa/etiqueta/faturável). A CLI Python se instala sozinha na primeira sessão
  (requer [`uv`](https://docs.astral.sh/uv/)).
- Funciona em **macOS, Windows e Linux**. A única dependência é o **`uv`** —
  **não precisa ter Python instalado** (o `uv` baixa um Python gerenciado sozinho). Instalar `uv`:
  - macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - Se você não tiver `uv`, o `/clockify-setup` se oferece para instalá-lo.
- Sua config fica em `~/.config/clockify-horas/config.json` (macOS/Linux) ou
  `%APPDATA%\clockify-horas\config.json` (Windows) — só sua, fora do repo.

## Uso

- `/horas` (ou `/horas 2026-01-28`) — lança um dia a partir da agenda do Outlook.
- `/lancar` — lança vários dias de uma vez (ex: mês retroativo). Funciona sem ICS.

## CLI direta

```bash
clockify-horas config show
clockify-horas config doctor
clockify-horas agenda --date 2026-01-28
clockify-horas meta
clockify-horas entries --date 2026-01-28
clockify-horas business-days --start 2026-05-01 --end 2026-05-31
clockify-horas add --file lancamentos.json --dry-run
```

## Config (gerada pelo /clockify-setup)

Local: `~/.config/clockify-horas/config.json` (macOS/Linux) ou
`%APPDATA%\clockify-horas\config.json` (Windows).

```json
{
  "clockify": { "api_key": "...", "workspace_id": "..." },
  "outlook":  { "ics_url": "..." },
  "defaults": { "task_name": "...", "tag_name": "...", "billable": false, "daily_target_hours": 8.0 },
  "overrides": []
}
```

Variáveis de ambiente (`CLOCKIFY_API_KEY`, `CLOCKIFY_WORKSPACE_ID`, `OUTLOOK_ICS_URL`) têm
precedência sobre o arquivo (útil em CI).

## Dev

```bash
uv sync
uv run pytest -q
uv run ruff check .
uv run pyright
```

Mantenedor: ver `MAINTAINER.md`.
```

- [ ] **Step 3: Commit**

```bash
git add MAINTAINER.md README.md
git commit -m "docs: README para time + MAINTAINER.md"
```

---

### Task 16: Validação estática do plugin

- [ ] **Step 1: Validar manifesto + suíte**

Run: `claude plugin validate . ; uv run pytest -q && uv run ruff check . && uv run pyright`
Expected: validate sem erros; suíte verde. (Se `claude plugin validate` indisponível, registre e siga para o dogfood.)

- [ ] **Step 2: Verificação final de ausência de dado pessoal no pacote**

Run: `git ls-files | grep -vE '^docs/|^tests/' | xargs grep -lniE "san pablo|mulesoft|farmacia|vbjuliani@gmail" 2>/dev/null ; echo "exit $?"`
Expected: nenhum arquivo (exit 1). `docs/` e `tests/` ficam de fora porque podem citar exemplos históricos; confirme que nenhum arquivo **distribuível** (commands/skills/src/manifests) aparece.

---

## PHASE 5 — Dogfood (validação ponta a ponta)

### Task 17: Autor reinstala como plugin e valida o onboarding

> Este é manual — não há teste automatizado de slash command. Marque cada item ao confirmar.

- [ ] **Step 1:** Em uma sessão limpa do Claude Code, rodar `/plugin marketplace add <caminho-local-deste-repo>` e `/plugin install clockify-horas@pg-clockify`. Confirmar que aparece sem erro.
- [ ] **Step 2:** Reabrir a sessão; confirmar no stderr/log que o SessionStart hook instalou a CLI (`clockify-horas --help` funciona num terminal).
- [ ] **Step 3:** Rodar `/clockify-setup` do zero. Conferir: descobre workspace, lista tarefas/etiquetas numeradas, grava `~/.config/clockify-horas/config.json`, e `config doctor` termina com `OK` (key+workspace).
- [ ] **Step 4:** Re-cadastrar manualmente o override pessoal (San Pablo/Mulesoft) via o passo de overrides do setup — confirmando que ele vive só na config local, não no repo.
- [ ] **Step 5:** Rodar `/horas <hoje>` até o **dry-run** (sem gravar) e conferir que defaults + overrides aplicam corretamente.
- [ ] **Step 6:** Rodar `/lancar` para um intervalo curto até o dry-run (sem gravar).
- [ ] **Step 7:** Confirmar o `marketplace.json source`: se `"."` não tiver funcionado no Step 1, mover o plugin para `plugins/clockify-horas/` e ajustar `source`, recommitar, e repetir o Step 1.
- [ ] **Step 8 (cross-platform):** se houver um colega em **Windows** disponível, validar lá os passos 1-6 (instala via `/plugin install`, hook roda `uv run --script` no cmd/PowerShell, config grava em `%APPDATA%\clockify-horas\config.json`, `/horas` e `/lancar` até dry-run). Se não houver, registrar como pendência conhecida e, no mínimo, conferir que o comando do hook (`uv run --script "..."`) não depende de bash. macOS/Linux já cobertos pelos passos 1-7.
- [ ] **Step 9 (verification-before-completion):** `uv run pytest -q && uv run ruff check . && uv run pyright` verdes; `git status` limpo. Declarar pronto só com essas evidências.

---

## Self-Review (preenchido na escrita)

- **Cobertura do spec:** config XDG (Task 1-3), subcomando config set/show/path/add-override/doctor (Task 4-7), ICS opcional/guard (Task 2,8), generalização commands (Task 9), remoção de dado pessoal (Task 9,10,16), skill setup (Task 11), plugin.json/marketplace/hook (Task 12-14), MAINTAINER/README (Task 15), dogfood (Task 17). Sem requisito órfão.
- **Overrides são do autor apenas:** garantido — pacote sai com `overrides: []` (Task 14 não cria override; setup só adiciona localmente; Step 4 do dogfood recadastra na config local).
- **Consistência de tipos:** `read_raw`/`write_raw`/`config_path`/`load_config`/`load_defaults`/`load_overrides`/`Override` usados de forma idêntica entre Tasks 1-7. Subcomandos chamam `read_raw`/`write_raw` de `config.py`.
- **Cross-platform (macOS/Windows/Linux):** `config_path` trata `%APPDATA%` no Windows (Task 1); `write_raw` faz `chmod 600` só em POSIX e o teste guarda a asserção (Task 1); bootstrap em Python via `uv run --script`, não bash (Task 13); `/clockify-setup` instrui `uv` por SO (Task 11); dogfood inclui passo Windows (Task 17, Step 8).
- **Universalidade (sem Python pré-instalado):** única dependência é `uv`, que baixa Python gerenciado tanto em `uv tool install` quanto em `uv run --script` (Task 13). Hook não instala `uv` sozinho; `/clockify-setup` oferece instalar com consentimento (Task 11).
- **Correções do plan-critic (rodada 1):** C1 (doctor usa `load_config(use_dotenv=False)`, que não chama `load_dotenv()` — Task 7) e C2 (versão lida do `plugin.json`, fonte única, alinhada ao `MAINTAINER.md` — Tasks 13,15). W1/W2 (cobertura do doctor: defaults completos + mock de metadata + teste de ICS — Task 7). W5/W6 (acoplamento do fallback de `source` e formatos do manifesto — Tasks 12,14).
- **Correções do plan-critic (rodada 2, pós cross-platform):** C1-bis (teste do `agenda` na Task 8 usa `setenv("OUTLOOK_ICS_URL", "")` em vez de `delenv` — `load_dotenv()` faz descoberta de `.env` por **frame**, não cwd, então `chdir` não bastaria; var presente+vazia + `override=False` mantém o guard hermético). W1-bis (`MAINTAINER.md` referenciava `ensure-cli.sh` → corrigido para `ensure_cli.py`). W2-bis (spec §Fluxo/§Componentes diziam que a skill instala a CLI — reconciliado: hook instala, skill só oferece `uv`).
- **Incerteza registrada:** `marketplace.json` com `source: "."` (Task 14) e disponibilidade de `claude plugin validate` (Task 12,16) — ambos com fallback explícito no dogfood; validação no Windows depende de colega disponível (Task 17, Step 8).
```
