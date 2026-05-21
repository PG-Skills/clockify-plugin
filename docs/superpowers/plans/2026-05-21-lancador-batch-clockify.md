# Lançador Batch Multi-dia Clockify — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir lançar horas no Clockify em vários dias de uma vez (ex: maio retroativo), via slash command `/lancar`, com seleção de dias úteis e anti-duplicata por intervalo.

**Architecture:** Estende o `clockify-horas` existente. Reusa `add` (já grava entries multi-data) para a escrita. Adiciona uma função pura `business_days`, um subcomando CLI `business-days`, um método de cliente `get_entries_for_range` e a opção `--start/--end` no subcomando `entries`. A orquestração da conversa multi-dia vive no slash command `/lancar`.

**Tech Stack:** Python 3.12+, uv, ruff, pyright, httpx, pytest + respx. (Mesma stack do projeto base.)

---

## File Structure

```
src/clockify_horas/
├── bizdays.py        # NOVO — business_days(start, end) puro
├── clockify_api.py   # MODIFICADO — get_entries_for_range
└── cli.py            # MODIFICADO — subcomando business-days; entries --start/--end
tests/
├── test_bizdays.py        # NOVO
├── test_clockify_api.py   # MODIFICADO — teste de get_entries_for_range
└── test_cli.py            # MODIFICADO — business-days; entries intervalo
.claude/commands/
└── lancar.md         # NOVO — orquestração /lancar
```

Responsabilidades: `bizdays` (lógica pura de datas), `clockify_api` (toda chamada HTTP), `cli` (wiring), `lancar.md` (conversa). Escrita reusa `add` sem alteração.

---

## Task 1: Função pura `business_days`

**Files:**
- Create: `src/clockify_horas/bizdays.py`
- Test: `tests/test_bizdays.py`

- [ ] **Step 1: Escrever teste falho `tests/test_bizdays.py`**

```python
from datetime import date

import pytest

from clockify_horas.bizdays import business_days


def test_business_days_exclui_fim_de_semana():
    # 2026-05-01 (sex) a 2026-05-07 (qui): pula 02 (sáb) e 03 (dom)
    dias = business_days(date(2026, 5, 1), date(2026, 5, 7))
    assert dias == [
        date(2026, 5, 1),
        date(2026, 5, 4),
        date(2026, 5, 5),
        date(2026, 5, 6),
        date(2026, 5, 7),
    ]


def test_business_days_intervalo_de_um_dia_util():
    assert business_days(date(2026, 5, 4), date(2026, 5, 4)) == [date(2026, 5, 4)]


def test_business_days_um_dia_fim_de_semana_vazio():
    assert business_days(date(2026, 5, 2), date(2026, 5, 2)) == []


def test_business_days_start_depois_de_end_levanta():
    with pytest.raises(ValueError, match="start"):
        business_days(date(2026, 5, 10), date(2026, 5, 1))
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_bizdays.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'clockify_horas.bizdays'`.

- [ ] **Step 3: Implementar `src/clockify_horas/bizdays.py`**

```python
from datetime import date, timedelta


def business_days(start: date, end: date) -> list[date]:
    """Lista as datas seg–sex no intervalo [start, end] (inclusive).

    Não filtra feriados — isso é podado manualmente na conversa do /lancar.
    Levanta ValueError se start > end.
    """
    if start > end:
        raise ValueError(f"start ({start}) não pode ser depois de end ({end})")
    dias: list[date] = []
    atual = start
    while atual <= end:
        if atual.weekday() < 5:  # 0=seg ... 4=sex; 5=sáb, 6=dom
            dias.append(atual)
        atual += timedelta(days=1)
    return dias
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_bizdays.py -v`
Expected: PASS — 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/bizdays.py tests/test_bizdays.py
git commit -m "feat: business_days lista dias úteis de um intervalo"
```

---

## Task 2: Subcomando CLI `business-days`

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Escrever teste falho em `tests/test_cli.py`**

Adicionar ao final do arquivo (o import `json` e `main` já existem no topo):

```python
def test_business_days_imprime_json(capsys):
    rc = main(["business-days", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == ["2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07"]
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_cli.py::test_business_days_imprime_json -v`
Expected: FAIL — `SystemExit: 2` (argumento `business-days` inválido / subparser inexistente).

- [ ] **Step 3: Implementar em `src/clockify_horas/cli.py`**

Adicionar o import no topo (junto aos demais `from clockify_horas...`):

```python
from clockify_horas.bizdays import business_days
```

Adicionar a função de comando (após `_cmd_entries`):

```python
def _cmd_business_days(args: argparse.Namespace) -> int:
    dias = business_days(date.fromisoformat(args.start), date.fromisoformat(args.end))
    print(json.dumps([d.isoformat() for d in dias], ensure_ascii=False, indent=2))
    return 0
```

Registrar o subparser dentro de `build_parser()` (antes do `return parser`):

```python
    p_bd = sub.add_parser("business-days", help="Lista dias úteis (seg–sex) de um intervalo")
    p_bd.add_argument("--start", required=True, help="AAAA-MM-DD")
    p_bd.add_argument("--end", required=True, help="AAAA-MM-DD")
    p_bd.set_defaults(func=_cmd_business_days)
```

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_cli.py::test_business_days_imprime_json -v`
Expected: PASS — 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_cli.py
git commit -m "feat: subcomando CLI business-days"
```

---

## Task 3: `ClockifyClient.get_entries_for_range`

**Files:**
- Modify: `src/clockify_horas/clockify_api.py`
- Test: `tests/test_clockify_api.py`

- [ ] **Step 1: Escrever teste falho em `tests/test_clockify_api.py`**

Adicionar ao final (os imports `date`, `ZoneInfo`, `httpx`, `respx`, `BASE`, `TZ`, `_client` já existem no topo):

```python
@respx.mock
def test_get_entries_for_range_usa_janela_utc():
    route = respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[{"id": "e1"}])
    )
    entries = _client().get_entries_for_range("u1", date(2026, 5, 1), date(2026, 5, 7), TZ)
    assert entries == [{"id": "e1"}]
    sent = route.calls.last.request
    # 01/05 00:00 local (UTC-3) -> 03:00Z; fim = 08/05 00:00 local -> 03:00Z (end+1 dia)
    assert sent.url.params["start"] == "2026-05-01T03:00:00Z"
    assert sent.url.params["end"] == "2026-05-08T03:00:00Z"
    assert sent.url.params["page-size"] == "1000"
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_clockify_api.py::test_get_entries_for_range_usa_janela_utc -v`
Expected: FAIL — `AttributeError: 'ClockifyClient' object has no attribute 'get_entries_for_range'`.

- [ ] **Step 3: Implementar em `src/clockify_horas/clockify_api.py`**

Adicionar o método na classe `ClockifyClient` (após `get_entries_for_date`):

```python
    def get_entries_for_range(
        self, user_id: str, start: date, end: date, tz: ZoneInfo
    ) -> list[dict[str, Any]]:
        """Lançamentos do usuário no intervalo de dias locais [start, end] (inclusive).

        Janela: 00:00 local de ``start`` até 00:00 local do dia seguinte a ``end``,
        convertida para instantes UTC. page-size alto para cobrir um mês numa chamada.
        """
        win_start = datetime.combine(start, time.min, tzinfo=tz).astimezone(UTC)
        win_end = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz).astimezone(UTC)
        return self._get(
            f"/workspaces/{self.workspace_id}/user/{user_id}/time-entries",
            params={
                "start": win_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": win_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "page-size": 1000,
            },
        )
```

> Nota: `date`, `time`, `timedelta`, `UTC`, `ZoneInfo` e `Any` já estão importados no topo
> de `clockify_api.py` (usados por `get_entries_for_date`). Nenhum import novo é necessário.

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_clockify_api.py::test_get_entries_for_range_usa_janela_utc -v`
Expected: PASS — 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/clockify_horas/clockify_api.py tests/test_clockify_api.py
git commit -m "feat: get_entries_for_range para anti-duplicata por intervalo"
```

---

## Task 4: `entries --start/--end` (intervalo, agrupado por data)

**Files:**
- Modify: `src/clockify_horas/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Escrever teste falho em `tests/test_cli.py`**

Adicionar ao final:

```python
@respx.mock
def test_entries_intervalo_agrupa_por_data(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "e1",
                    "description": "Dev",
                    "timeInterval": {"start": "2026-05-04T12:00:00Z", "end": "2026-05-04T21:00:00Z"},
                },
                {
                    "id": "e2",
                    "description": "Reunião",
                    "timeInterval": {"start": "2026-05-05T13:00:00Z", "end": "2026-05-05T14:00:00Z"},
                },
            ],
        )
    )
    rc = main(["entries", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    # agrupado por data LOCAL (UTC-3): 12:00Z -> 09:00 de 04/05
    assert set(out.keys()) == {"2026-05-04", "2026-05-05"}
    assert out["2026-05-04"][0]["description"] == "Dev"


def test_entries_exige_date_ou_intervalo(capsys):
    rc = main(["entries"])
    assert rc == 2  # nem --date nem --start/--end
    err = capsys.readouterr().err
    assert "date" in err.lower() or "start" in err.lower()
```

- [ ] **Step 2: Rodar para confirmar falha**

Run: `uv run pytest tests/test_cli.py -k "entries_intervalo or entries_exige" -v`
Expected: FAIL — `entries` ainda não aceita `--start/--end` nem valida ausência.

- [ ] **Step 3: Implementar em `src/clockify_horas/cli.py`**

Substituir a função `_cmd_entries` inteira por esta versão (que aceita dia único OU intervalo):

```python
def _cmd_entries(args: argparse.Namespace) -> int:
    """Lista lançamentos existentes — um dia (--date) ou intervalo (--start/--end).

    --date: imprime lista do dia. Intervalo: imprime objeto agrupado por data local.
    """
    if not args.date and not (args.start and args.end):
        print("erro: informe --date OU --start e --end", file=sys.stderr)
        return 2

    cfg = load_config()
    client = ClockifyClient(cfg.api_key, cfg.workspace_id)
    user_id = client.get_user_id()

    if args.start and args.end:
        existentes = client.get_entries_for_range(
            user_id, date.fromisoformat(args.start), date.fromisoformat(args.end), _TZ
        )
        por_data: dict[str, list[dict]] = {}
        for e in existentes:
            ini = e.get("timeInterval", {}).get("start")
            if not ini:
                continue
            local_date = datetime.fromisoformat(ini.replace("Z", "+00:00")).astimezone(_TZ).date()
            por_data.setdefault(local_date.isoformat(), []).append(
                {"id": e.get("id"), "description": e.get("description"), "start": ini}
            )
        print(json.dumps(por_data, ensure_ascii=False, indent=2))
        return 0

    target = date.fromisoformat(args.date) if args.date else date.today()
    existentes = client.get_entries_for_date(user_id, target, _TZ)
    resumo = [
        {
            "id": e.get("id"),
            "description": e.get("description"),
            "start": e.get("timeInterval", {}).get("start"),
            "end": e.get("timeInterval", {}).get("end"),
        }
        for e in existentes
    ]
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return 0
```

Atualizar o registro do subparser `entries` em `build_parser()` para aceitar os novos args.
Substituir o bloco atual do `p_entries` por:

```python
    p_entries = sub.add_parser("entries", help="Lista lançamentos (--date OU --start/--end)")
    p_entries.add_argument("--date", help="AAAA-MM-DD (um dia)")
    p_entries.add_argument("--start", help="AAAA-MM-DD (início do intervalo)")
    p_entries.add_argument("--end", help="AAAA-MM-DD (fim do intervalo)")
    p_entries.set_defaults(func=_cmd_entries)
```

A validação "nem --date nem intervalo" já está embutida no início da nova `_cmd_entries`
acima — retorna `2` (não levanta `SystemExit`), para o teste poder afirmar `rc == 2`.
`sys` já está importado no topo de `cli.py`.

- [ ] **Step 4: Rodar para confirmar PASS**

Run: `uv run pytest tests/test_cli.py -k "entries" -v`
Expected: PASS — todos os testes `entries` (o do dia único anterior + os 2 novos).

- [ ] **Step 5: Rodar suíte inteira + lint + typecheck**

Run: `uv run pytest -q && uv run ruff check . && uv run pyright`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add src/clockify_horas/cli.py tests/test_cli.py
git commit -m "feat: entries aceita intervalo (--start/--end) agrupado por data"
```

---

## Task 5: Slash command `/lancar`

**Files:**
- Create: `.claude/commands/lancar.md`

> Prompt de orquestração — não é código testável por unidade. Chama a CLI já testada.
> Validação manual no Task 6.

- [ ] **Step 1: Criar `.claude/commands/lancar.md`**

````markdown
---
description: Lança horas no Clockify em vários dias de uma vez (ex: maio retroativo)
---

Você vai lançar horas no Clockify em VÁRIOS dias de uma vez. Não há agenda do Outlook
para ler (uso típico: retroativo). Conduza em português, um passo de cada vez:

1. **Período.** Pergunte o intervalo (ex: "maio", "01–15/05"). Converta para datas
   AAAA-MM-DD e rode `uv run clockify-horas business-days --start <ini> --end <fim>`.
   Apresente os dias úteis listados.

2. **Podar exceções.** Pergunte quais dias remover (feriados, férias, dias sem trabalho).
   Remova-os da lista de trabalho.

3. **Anti-duplicata.** Rode `uv run clockify-horas entries --start <ini> --end <fim>`.
   Para cada dia que JÁ tem lançamento, AVISE e pergunte se pula ou soma.

4. **Ditar atividades.** Pergunte o que lançar. Aceite dois modos:
   - "mesma atividade em todos os dias restantes" → clone a mesma descrição + horários
     em cada dia ainda ativo;
   - por dia → o usuário dita descrição + início/fim de cada dia.
   Aplique os defaults de `defaults.json` (tarefa `Time IA`, tag `Célula de Inovação`,
   não-faturável). Aceite overrides de tarefa/etiqueta/faturável; valide nomes fora do
   default contra `uv run clockify-horas meta`.

5. **Revisão.** Mostre uma tabela por dia (data, descrição, horário, tarefa, tag,
   faturável, duração) e o total de horas por dia. Avise dias fora de ~8h (não bloqueie).

6. **Dry-run.** Monte UM JSON com todos os lançamentos de todos os dias, salve em arquivo
   temporário e rode `uv run clockify-horas add --file <tmp> --dry-run`. Mostre os payloads.
   Peça confirmação explícita.

7. **Gravar.** Só após "pode lançar", rode `uv run clockify-horas add --file <tmp>`
   (sem `--dry-run`). Reporte o resumo por dia.

Nunca pule a confirmação do passo 6. Nunca grave sem dry-run antes. Em lotes grandes
(mês inteiro), confirme o total de dias e de horas antes de gravar.
````

- [ ] **Step 2: Commit**

```bash
git add .claude/commands/lancar.md
git commit -m "feat: slash command /lancar para lançamento batch multi-dia"
```

---

## Task 6: README e validação manual

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Atualizar `README.md`**

Adicionar à seção "Uso" e à "CLI direta" o novo fluxo. Inserir após a linha do `/horas`:

```markdown
- `/lancar` — lança em vários dias de uma vez (ex: maio retroativo).
```

E na seção "CLI direta", adicionar:

```bash
uv run clockify-horas business-days --start 2026-05-01 --end 2026-05-31
uv run clockify-horas entries --start 2026-05-01 --end 2026-05-31
```

- [ ] **Step 2: Validação manual (com credenciais reais)**

- [ ] `uv run clockify-horas business-days --start 2026-05-01 --end 2026-05-31` lista os dias úteis de maio.
- [ ] `uv run clockify-horas entries --start 2026-05-01 --end 2026-05-31` mostra o que já está lançado (ex: o dia 21/05 já lançado nesta sessão), agrupado por data.
- [ ] `/lancar` em um intervalo curto de teste (ex: 2 dias), com `--dry-run`, mostra payloads corretos para ambos os dias.
- [ ] Gravar 1 dia de teste real e conferir na UI do Clockify; apagar depois.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README cobre /lancar e comandos de intervalo"
```

---

## Self-Review (preenchido)

**1. Spec coverage:**
- Seleção de dias úteis de um período → Tasks 1, 2 (`business_days` + CLI). ✅
- Usuário poda exceções → Task 5 (passo 2 do `/lancar`). ✅
- Conteúdo decidido por dia + atalho "mesma em todos" → Task 5 (passo 4). ✅
- Defaults `Time IA`/`Célula de Inovação`/não-faturável + overrides → reuso de `build_payload`; Task 5 passo 4. ✅
- Escrita multi-data → reuso de `add` (Task 5 passos 6-7). ✅
- Anti-duplicata por intervalo → Tasks 3 (`get_entries_for_range`), 4 (`entries --start/--end`), 5 (passo 3). ✅
- Dry-run obrigatório → Task 5 passos 6-7. ✅
- Período inválido (start>end) → Task 1 (`ValueError`). ✅
- Feriados não automatizados → poda manual, Task 5 passo 2 (consistente com spec). ✅

**2. Placeholder scan:** sem TBD/TODO; todo passo de código traz o código real.

**3. Type consistency:** `business_days(start: date, end: date) -> list[date]` usado igual em Tasks 1-2; `get_entries_for_range(user_id, start, end, tz)` igual em Tasks 3-4; `_cmd_entries` reescrito mantém o caminho `--date` já existente intacto. Imports reutilizados de `clockify_api.py` confirmados presentes (Task 3 nota).
