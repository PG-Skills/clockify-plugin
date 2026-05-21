import json

import httpx
import respx

from clockify_horas.cli import main

BASE = "https://api.clockify.me/api/v1"


def _setup_env(monkeypatch):
    monkeypatch.setenv("CLOCKIFY_API_KEY", "key123")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "ws1")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "https://x/cal.ics")


@respx.mock
def test_agenda_imprime_json(monkeypatch, capsys, sample_ics):
    _setup_env(monkeypatch)
    respx.get("https://x/cal.ics").mock(return_value=httpx.Response(200, text=sample_ics))
    rc = main(["agenda", "--date", "2026-01-28"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert [e["title"] for e in out] == ["Daily Time IA", "Reunião Cliente X"]
    assert out[0]["start"].startswith("2026-01-28T09:00")


# bare @respx.mock usa o singleton global (assert_all_called=False por padrão), então o
# POST registrado mas não chamado em dry-run não falha
@respx.mock
def test_add_dry_run_nao_posta(monkeypatch, capsys, tmp_path):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(
            200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}]
        )
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries")
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "description": "Reunião Cliente X",
                    "start": "2026-01-28T13:00:00-03:00",
                    "end": "2026-01-28T14:00:00-03:00",
                    "task_name": ".Célula de Inovação: Time IA",
                    "tag_names": ["Atividades Internas"],
                    "billable": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = main(["add", "--file", str(entries_file), "--dry-run"])
    assert rc == 0
    assert not post_route.called  # dry-run não posta
    out = capsys.readouterr().out
    assert "2026-01-28T16:00:00Z" in out  # payload convertido p/ UTC


@respx.mock
def test_add_real_posta(monkeypatch, tmp_path):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(
            200, json=[{"id": "t1", "name": ".Célula de Inovação: Time IA"}]
        )
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "new1"})
    )
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "description": "Reunião Cliente X",
                    "start": "2026-01-28T13:00:00-03:00",
                    "end": "2026-01-28T14:00:00-03:00",
                    "task_name": ".Célula de Inovação: Time IA",
                    "tag_names": ["Atividades Internas"],
                    "billable": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 0
    assert post_route.called


@respx.mock
def test_entries_lista_lancamentos_do_dia(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": "e1",
                    "description": "Já lançado",
                    "timeInterval": {
                        "start": "2026-01-28T16:00:00Z",
                        "end": "2026-01-28T17:00:00Z",
                    },
                }
            ],
        )
    )
    rc = main(["entries", "--date", "2026-01-28"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out[0]["description"] == "Já lançado"
    assert out[0]["start"] == "2026-01-28T16:00:00Z"


def test_business_days_imprime_json(capsys):
    rc = main(["business-days", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == ["2026-05-01", "2026-05-04", "2026-05-05", "2026-05-06", "2026-05-07"]


@respx.mock
def test_entries_intervalo_agrupa_por_data(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "e1", "description": "Dev",
                 "timeInterval": {"start": "2026-05-04T12:00:00Z", "end": "2026-05-04T21:00:00Z"}},
                {"id": "e2", "description": "Reunião",
                 "timeInterval": {"start": "2026-05-05T13:00:00Z", "end": "2026-05-05T14:00:00Z"}},
            ],
        )
    )
    rc = main(["entries", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert set(out.keys()) == {"2026-05-04", "2026-05-05"}
    assert out["2026-05-04"][0]["description"] == "Dev"


def test_entries_exige_date_ou_intervalo(capsys):
    rc = main(["entries"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "date" in err.lower() or "start" in err.lower()


@respx.mock
def test_entries_intervalo_borda_meia_noite(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "e1", "description": "Tarde do dia 7",
                 "timeInterval": {"start": "2026-05-08T02:00:00Z", "end": "2026-05-08T02:30:00Z"}},
            ],
        )
    )
    rc = main(["entries", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert list(out.keys()) == ["2026-05-07"]


@respx.mock
def test_entries_intervalo_vazio(monkeypatch, capsys):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/user/u1/time-entries").mock(
        return_value=httpx.Response(200, json=[])
    )
    rc = main(["entries", "--start", "2026-05-01", "--end", "2026-05-07"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {}


@respx.mock
def test_add_para_limpo_na_falha_parcial(monkeypatch, capsys, tmp_path):
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": "Time IA"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Célula de Inovação"}])
    )
    respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        side_effect=[httpx.Response(201, json={"id": "ok1"}), httpx.Response(500)]
    )
    entries_file = tmp_path / "e.json"
    entries_file.write_text(
        json.dumps(
            [
                {"description": "Dia 1", "start": "2026-05-04T09:00:00-03:00",
                 "end": "2026-05-04T10:00:00-03:00", "task_name": "Time IA",
                 "tag_names": ["Célula de Inovação"], "billable": False},
                {"description": "Dia 2", "start": "2026-05-05T09:00:00-03:00",
                 "end": "2026-05-05T10:00:00-03:00", "task_name": "Time IA",
                 "tag_names": ["Célula de Inovação"], "billable": False},
            ]
        ),
        encoding="utf-8",
    )
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "1/2" in err
