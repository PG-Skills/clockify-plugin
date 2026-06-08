# /clockify-report — Implementation Plan (lean)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Relatório read-only de horas lançadas no Clockify, fechando a v1.0. Dois modos: **diário** (escolhe 1 mês → horas dia a dia) e **mensal** (range de meses, máx 12 → totais por mês). i18n.

**Architecture:** A **agregação é determinística no CLI** (Python) — o LLM não soma horas nem faz conta de calendário. Novo subcomando `report` em `cli.py` que busca entries (reusa `clockify.entries`) e agrega com funções puras em `pure.py`. Skill `clockify-report` só verbaliza. Sem auth/escrita/endpoint — lean.

**Design (escopo v1):** horas **por dia** (modo diário) e **por mês** (modo mensal) + **total**. SEM quebra por projeto (evita resolver nomes de projeto / risco de timeout; é melhoria futura).

**Tech Stack:** Python 3.10+ stdlib. pytest dev. Markdown (command + skill).

---

## File Structure
```
clockify-cowork/scripts/clockify_cli/
├── pure.py    # ADD: month_window_utc, hours_by_day, hours_by_month, total_hours, _entry_seconds, _entry_local_dt
├── cli.py     # ADD: subcomando `report` + helper _parse_month
clockify-cowork/scripts/tests/
├── test_pure.py   # ADD testes de agregação
├── test_cli.py    # ADD testes do report
clockify-cowork/skills/clockify-report/SKILL.md   # CRIAR
clockify-cowork/commands/clockify-report.md        # CRIAR
```

---

## Task 1: Agregação pura em `pure.py`

**Files:** Modify `clockify_cli/pure.py`; add tests to `tests/test_pure.py`.

- [ ] **Step 1: Testes (falham)** — adicionar a `tests/test_pure.py`

```python
def test_month_window_utc():
    start, end = pure.month_window_utc(2026, 6, TZ)  # junho/2026
    assert start == "2026-06-01T03:00:00Z"   # 00:00 BRT = 03:00Z
    assert end == "2026-07-01T03:00:00Z"

def test_month_window_utc_december_rolls_year():
    start, end = pure.month_window_utc(2026, 12, TZ)
    assert start == "2026-12-01T03:00:00Z"
    assert end == "2027-01-01T03:00:00Z"

def _e(start, end):
    return {"timeInterval": {"start": start, "end": end}}

def test_hours_by_day_groups_local():
    entries = [
        _e("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z"),  # 1h, dia 01 (09-10 BRT)
        _e("2026-06-01T14:00:00Z", "2026-06-01T16:00:00Z"),  # 2h, dia 01
        _e("2026-06-02T12:00:00Z", "2026-06-02T12:30:00Z"),  # 0.5h, dia 02
    ]
    assert pure.hours_by_day(entries, TZ) == [
        {"date": "2026-06-01", "hours": 3.0},
        {"date": "2026-06-02", "hours": 0.5},
    ]

def test_hours_by_month_groups_local():
    entries = [
        _e("2026-01-15T12:00:00Z", "2026-01-15T20:00:00Z"),  # 8h jan
        _e("2026-02-10T12:00:00Z", "2026-02-10T16:00:00Z"),  # 4h fev
        _e("2026-02-11T12:00:00Z", "2026-02-11T13:00:00Z"),  # 1h fev
    ]
    assert pure.hours_by_month(entries, TZ) == [
        {"month": "2026-01", "hours": 8.0},
        {"month": "2026-02", "hours": 5.0},
    ]

def test_total_hours_and_skip_open_entries():
    entries = [
        _e("2026-06-01T12:00:00Z", "2026-06-01T13:00:00Z"),  # 1h
        {"timeInterval": {"start": "2026-06-01T14:00:00Z"}},  # sem end -> ignorado
        {"timeInterval": {}},                                   # vazio -> ignorado
    ]
    assert pure.total_hours(entries) == 1.0
    assert pure.hours_by_day(entries, TZ) == [{"date": "2026-06-01", "hours": 1.0}]

def test_local_grouping_crosses_utc_midnight():
    # 2026-06-02T01:00:00Z = 2026-06-01 22:00 BRT -> conta no dia 01 (local)
    entries = [_e("2026-06-02T01:00:00Z", "2026-06-02T02:00:00Z")]
    assert pure.hours_by_day(entries, TZ) == [{"date": "2026-06-01", "hours": 1.0}]
```
(`TZ = ZoneInfo("America/Sao_Paulo")` já está no topo de test_pure.py.)

- [ ] **Step 2: Rodar — falha.** `cd clockify-cowork/scripts && python3 -m pytest tests/test_pure.py -q` → FAIL.

- [ ] **Step 3: Implementar em `pure.py`** (acrescentar ao fim)

```python
def month_window_utc(year: int, month: int, tz: ZoneInfo) -> tuple[str, str]:
    """Janela `(start, end)` ISO UTC cobrindo o mês LOCAL (year, month): 00:00 do dia 1
    até 00:00 do dia 1 do mês seguinte, em UTC."""
    first = datetime(year, month, 1, tzinfo=tz)
    nxt = (
        datetime(year + 1, 1, 1, tzinfo=tz)
        if month == 12
        else datetime(year, month + 1, 1, tzinfo=tz)
    )
    return (
        first.astimezone(timezone.utc).strftime(_UTC_FMT),
        nxt.astimezone(timezone.utc).strftime(_UTC_FMT),
    )


def _entry_seconds(entry: dict) -> float:
    """Duração (segundos) de um time-entry cru; 0 se faltar start/end (entry em aberto)."""
    ti = entry.get("timeInterval") or {}
    start, end = ti.get("start"), ti.get("end")
    if not start or not end:
        return 0.0
    s = datetime.fromisoformat(start.replace("Z", "+00:00"))
    e = datetime.fromisoformat(end.replace("Z", "+00:00"))
    return max(0.0, (e - s).total_seconds())


def _entry_local_dt(entry: dict, tz: ZoneInfo) -> datetime | None:
    """Início do entry em hora LOCAL (para agrupar por dia/mês local)."""
    start = (entry.get("timeInterval") or {}).get("start")
    if not start:
        return None
    return datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(tz)


def total_hours(entries: list[dict]) -> float:
    """Total de horas (2 casas) somando as durações brutas (evita drift de arredondamento)."""
    return round(sum(_entry_seconds(e) for e in entries) / 3600, 2)


def hours_by_day(entries: list[dict], tz: ZoneInfo) -> list[dict]:
    """`[{date, hours}]` por dia LOCAL (só dias com horas > 0), ordenado por data."""
    acc: dict[str, float] = {}
    for e in entries:
        dt = _entry_local_dt(e, tz)
        secs = _entry_seconds(e)
        if dt is None or secs <= 0:
            continue
        acc[dt.date().isoformat()] = acc.get(dt.date().isoformat(), 0.0) + secs
    return [{"date": k, "hours": round(v / 3600, 2)} for k, v in sorted(acc.items())]


def hours_by_month(entries: list[dict], tz: ZoneInfo) -> list[dict]:
    """`[{month "YYYY-MM", hours}]` por mês LOCAL (só meses com horas > 0), ordenado."""
    acc: dict[str, float] = {}
    for e in entries:
        dt = _entry_local_dt(e, tz)
        secs = _entry_seconds(e)
        if dt is None or secs <= 0:
            continue
        key = f"{dt.year:04d}-{dt.month:02d}"
        acc[key] = acc.get(key, 0.0) + secs
    return [{"month": k, "hours": round(v / 3600, 2)} for k, v in sorted(acc.items())]
```

- [ ] **Step 4: Rodar — passa.** `cd clockify-cowork/scripts && python3 -m pytest tests/test_pure.py -q` → PASS.

- [ ] **Step 5: Commit**
```bash
git add clockify-cowork/scripts/clockify_cli/pure.py clockify-cowork/scripts/tests/test_pure.py
git commit -m "feat(cli): agregação de horas por dia/mês (pure) para o report"
```

---

## Task 2: Subcomando `report` no CLI

**Files:** Modify `clockify_cli/cli.py`; add tests to `tests/test_cli.py`.

Contrato (JSON):
- `report --month YYYY-MM` (diário) → `{"mode":"daily","month":"YYYY-MM","total_hours":H,"days":[{date,hours}]}`
- `report --start YYYY-MM --end YYYY-MM` (mensal, ≤12 meses) → `{"mode":"monthly","total_hours":H,"months":[{month,hours}]}`
- range > 12 meses ou invertido → `{"error":"INVALID_INPUT","reason":...}` (exit 2)
- nem `--month` nem (`--start`+`--end`) → `INVALID_INPUT`
- sem chave → `NO_KEY`; mês malformado → `INVALID_INPUT` (via ValueError no outer try)

- [ ] **Step 1: Testes (falham)** — adicionar a `tests/test_cli.py`

```python
def test_report_no_key(monkeypatch, tmp_path):
    monkeypatch.setenv("CLOCKIFY_DIR", str(tmp_path))
    code, out = _run(["report", "--month", "2026-06"])
    assert code == 3 and out == {"error": "NO_KEY"}


def test_report_daily(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    monkeypatch.setattr(clockify, "get_user", lambda k: (_ for _ in ()).throw(AssertionError("cache")))
    monkeypatch.setattr(clockify, "entries", lambda key, ws, uid, s, e: [
        {"timeInterval": {"start": "2026-06-01T12:00:00Z", "end": "2026-06-01T13:00:00Z"}},
    ])
    code, out = _run(["report", "--month", "2026-06"])
    assert code == 0 and out["mode"] == "daily" and out["month"] == "2026-06"
    assert out["total_hours"] == 1.0 and out["days"] == [{"date": "2026-06-01", "hours": 1.0}]


def test_report_monthly(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    monkeypatch.setattr(clockify, "entries", lambda key, ws, uid, s, e: [
        {"timeInterval": {"start": "2026-01-15T12:00:00Z", "end": "2026-01-15T20:00:00Z"}},
    ])
    code, out = _run(["report", "--start", "2026-01", "--end", "2026-03"])
    assert code == 0 and out["mode"] == "monthly"
    assert out["total_hours"] == 8.0 and out["months"] == [{"month": "2026-01", "hours": 8.0}]


def test_report_range_over_12_months(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report", "--start", "2025-01", "--end", "2026-02"])  # 14 meses
    assert code == 2 and out["error"] == "INVALID_INPUT" and out["reason"] == "max_12_meses"


def test_report_requires_mode(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report"])
    assert code == 2 and out["error"] == "INVALID_INPUT"


def test_report_malformed_month(monkeypatch, tmp_path):
    _seed_creds(monkeypatch, tmp_path)
    code, out = _run(["report", "--month", "2026/06"])
    assert code == 2 and out["error"] == "INVALID_INPUT"
```
> Nota: o `_seed_creds` já grava `workspace_id`+`user_id`, então `_account` não chama `get_user` (cache completo). Em `test_report_daily` o `get_user` é trocado por um que estoura, garantindo que NÃO é chamado.

- [ ] **Step 2: Rodar — falha.** `cd clockify-cowork/scripts && python3 -m pytest tests/test_cli.py -q` → FAIL.

- [ ] **Step 3: Implementar no `cli.py`**

Adicionar o helper (perto dos outros helpers de topo):
```python
def _parse_month(s: str) -> tuple[int, int]:
    """'YYYY-MM' -> (year, month). ValueError se malformado (cai em INVALID_INPUT)."""
    parts = s.split("-")
    if len(parts) != 2:
        raise ValueError(f"mês inválido: {s}")
    y, m = int(parts[0]), int(parts[1])
    if not (1 <= m <= 12):
        raise ValueError(f"mês inválido: {s}")
    return y, m
```
Registrar o subparser em `build_parser` (perto do `agenda`):
```python
    rp = sub.add_parser("report")
    rp.add_argument("--month")
    rp.add_argument("--start")
    rp.add_argument("--end")
```
Adicionar o branch em `main` (antes do `prefs`):
```python
        if args.cmd == "report":
            from zoneinfo import ZoneInfo
            tz = ZoneInfo("America/Sao_Paulo")
            creds = _load_key(stdout)
            if creds is None:
                return EXIT_NO_KEY
            acct = _account(creds, stdout)
            if acct is None:
                return EXIT_INVALID_KEY
            ws, uid = acct
            if args.month:  # modo diário
                y, m = _parse_month(args.month)
                w_start, w_end = pure.month_window_utc(y, m, tz)
                ents = clockify.entries(creds["api_key"], ws, uid, w_start, w_end)
                _emit({"mode": "daily", "month": args.month,
                       "total_hours": pure.total_hours(ents),
                       "days": pure.hours_by_day(ents, tz)}, stdout)
                return EXIT_OK
            if args.start and args.end:  # modo mensal
                sy, sm = _parse_month(args.start)
                ey, em = _parse_month(args.end)
                n = (ey - sy) * 12 + (em - sm) + 1
                if n < 1:
                    _emit({"error": "INVALID_INPUT", "reason": "intervalo_invertido"}, stdout)
                    return EXIT_UNKNOWN
                if n > 12:
                    _emit({"error": "INVALID_INPUT", "reason": "max_12_meses"}, stdout)
                    return EXIT_UNKNOWN
                w_start, _ = pure.month_window_utc(sy, sm, tz)
                _, w_end = pure.month_window_utc(ey, em, tz)
                ents = clockify.entries(creds["api_key"], ws, uid, w_start, w_end)
                _emit({"mode": "monthly",
                       "total_hours": pure.total_hours(ents),
                       "months": pure.hours_by_month(ents, tz)}, stdout)
                return EXIT_OK
            _emit({"error": "INVALID_INPUT", "reason": "use --month OU --start e --end"}, stdout)
            return EXIT_UNKNOWN
```
> `_parse_month` lança `ValueError` em mês malformado → cai no `except ValueError` do `main` → `INVALID_INPUT` (já existe). O `>12`/invertido emitem `INVALID_INPUT` direto.

- [ ] **Step 4: Rodar — passa.** `cd clockify-cowork/scripts && python3 -m pytest -q` → tudo verde.

- [ ] **Step 5: Commit**
```bash
git add clockify-cowork/scripts/clockify_cli/cli.py clockify-cowork/scripts/tests/test_cli.py
git commit -m "feat(cli): subcomando report (diário por mês / mensal por range ≤12)"
```

---

## Task 3: Skill `clockify-report` + command

**Files:** Create `clockify-cowork/skills/clockify-report/SKILL.md`; create `clockify-cowork/commands/clockify-report.md`. (Sem testes unitários — smoke.)

- [ ] **Step 1: Criar `skills/clockify-report/SKILL.md`**

```markdown
---
name: clockify-report
description: Mostra um relatório das horas lançadas no Clockify (diário por mês, ou mensal por um intervalo de meses), conversando na língua da pessoa.
---

Você mostra à pessoa um relatório das horas que ela já lançou no Clockify. **Converse SEMPRE
na língua da pessoa.** O CLI devolve **JSON**; **você** verbaliza. **Nunca** mostre JSON/IDs/jargão.

## Como rodar o CLI
Igual à skill `clockify-tracking`: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli <cmd>`.
Se o terminal não enxergar o plugin, use a cópia local **atualizada** (sempre
`rm -rf .clockify/bin/clockify_cli` + recopiar os `.py` de `${CLAUDE_PLUGIN_ROOT}/scripts/clockify_cli/`
com ferramentas de arquivo + rodar com `python3 -B .clockify/bin/clockify_cli`). Nunca reuse cópia velha.

## Pré-requisitos
1. **Projeto (pasta local):** rode `pwd`; se for temporário (`/sessions/...` sem `/mnt/`) ou
   `CLAUDE_PROJECT_DIR` vazio, peça pra pessoa abrir um projeto (igual ao tracking) e pare.
2. **Conexão:** o report usa a chave já conectada. Se um comando voltar `{"error":"NO_KEY"}`,
   diga que precisa conectar primeiro (rode `/clockify` ou `/clockify-tracking`) e pare.

## Datas — pelo sistema, nunca de cabeça
Você erra calendário. Pegue o "hoje" real (`date +"%Y-%m"`) e resolva meses pelo `date` do
terminal quando a pessoa falar relativo ("mês passado", "últimos 3 meses"): ex.
`date -d "last month" +%Y-%m`. **Confirme com a pessoa o(s) mês(es) antes de gerar.**

## Fluxo
1. Pergunte: **"Quer ver dia a dia de um mês, ou um resumo mensal de vários meses?"**
2. **Diário:** pergunte qual mês → resolva/confirme (AAAA-MM) → rode
   `... report --month AAAA-MM`. Apresente uma lista limpa: cada dia com horas (formate
   bonito, ex. "8h", "7h30") e o **total** do mês. Dias sem lançamento simplesmente não
   aparecem (mencione se a pessoa perguntar).
3. **Mensal:** pergunte o intervalo de meses (**máx 12**) → resolva/confirme início e fim →
   rode `... report --start AAAA-MM --end AAAA-MM`. Apresente cada mês com seu total + o
   total geral. Se vier `{"error":"INVALID_INPUT","reason":"max_12_meses"}`, explique gentil
   que o limite é 12 meses e peça um intervalo menor.
4. Formate horas de forma humana (ex.: 7.5 → "7h30", 8.0 → "8h"). Nunca despeje números crus
   sem contexto nem JSON.

**Regras de ouro:** resolva meses pelo sistema e confirme antes; nunca mostre JSON/IDs;
fale na língua da pessoa; o report é só leitura (não grava nada).
```

- [ ] **Step 2: Criar `commands/clockify-report.md`**

```markdown
---
description: Mostra um relatório das horas lançadas no Clockify (diário ou mensal)
---

Use a skill **clockify-report** para mostrar o relatório de horas do Clockify (diário de um
mês, ou mensal de um intervalo de meses ≤ 12), na língua da pessoa, só leitura. Siga a skill.
```

- [ ] **Step 3: Commit**
```bash
git add clockify-cowork/skills/clockify-report clockify-cowork/commands/clockify-report.md
git commit -m "feat(skill): /clockify-report (diário/mensal, i18n, read-only)"
```

---

## Self-Review
- **Cobertura:** modo diário (Task 1 `hours_by_day` + Task 2 `--month`); mensal ≤12 (Task 1 `hours_by_month` + Task 2 `--start/--end` + guard 12); i18n + datas-pelo-sistema + fallback CLI (Task 3 skill). ✅
- **Determinismo:** agregação e janelas de mês são puras/testadas; o LLM não soma nem calcula data. ✅
- **3.10:** `timezone.utc`, datetimes via `fromisoformat` em timestamps COMPLETOS do Clockify (com offset) — ok no 3.10; nada de `datetime.UTC`. ✅
- **Consistência:** `report` reusa `_load_key`/`_account`/`clockify.entries`/`pure.*` e os códigos de saída/erros existentes (`NO_KEY`/`INVALID_KEY`/`INVALID_INPUT`/`HTTP_ERROR`). ✅
- **Escopo:** sem quebra por projeto (futuro), sem auth/escrita — lean. ✅
```
