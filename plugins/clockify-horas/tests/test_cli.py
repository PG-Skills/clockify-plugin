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
    assert [e["title"] for e in out] == ["Daily Equipe Demo", "Reunião Cliente X"]
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
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Etiqueta Demo: Equipe Demo"}])
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
                    "task_name": ".Etiqueta Demo: Equipe Demo",
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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Etiqueta Demo: Equipe Demo"}])
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
                    "task_name": ".Etiqueta Demo: Equipe Demo",
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
                {
                    "id": "e1",
                    "description": "Dev",
                    "timeInterval": {
                        "start": "2026-05-04T12:00:00Z",
                        "end": "2026-05-04T21:00:00Z",
                    },
                },
                {
                    "id": "e2",
                    "description": "Reunião",
                    "timeInterval": {
                        "start": "2026-05-05T13:00:00Z",
                        "end": "2026-05-05T14:00:00Z",
                    },
                },
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
                {
                    "id": "e1",
                    "description": "Tarde do dia 7",
                    "timeInterval": {
                        "start": "2026-05-08T02:00:00Z",
                        "end": "2026-05-08T02:30:00Z",
                    },
                },
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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": "Equipe Demo"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Etiqueta Demo"}])
    )
    respx.post(f"{BASE}/workspaces/ws1/time-entries").mock(
        side_effect=[httpx.Response(201, json={"id": "ok1"}), httpx.Response(500)]
    )
    entries_file = tmp_path / "e.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "description": "Dia 1",
                    "start": "2026-05-04T09:00:00-03:00",
                    "end": "2026-05-04T10:00:00-03:00",
                    "task_name": "Equipe Demo",
                    "tag_names": ["Etiqueta Demo"],
                    "billable": False,
                },
                {
                    "description": "Dia 2",
                    "start": "2026-05-05T09:00:00-03:00",
                    "end": "2026-05-05T10:00:00-03:00",
                    "task_name": "Equipe Demo",
                    "tag_names": ["Etiqueta Demo"],
                    "billable": False,
                },
            ]
        ),
        encoding="utf-8",
    )
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "1/2" in err


@respx.mock
def test_add_arquivo_inexistente_rc1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _setup_env(monkeypatch)
    rc = main(["add", "--file", str(tmp_path / "nao_existe.json")])
    assert rc == 1
    err = capsys.readouterr().err
    assert (
        "não encontrado" in err.lower() or "not found" in err.lower() or "nao_existe" in err.lower()
    )


@respx.mock
def test_add_item_sem_tag_names_rc1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": ".Etiqueta Demo: Equipe Demo"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "description": "Reunião Cliente X",
                    "start": "2026-01-28T13:00:00-03:00",
                    "end": "2026-01-28T14:00:00-03:00",
                    "task_name": ".Etiqueta Demo: Equipe Demo",
                    # tag_names ausente propositalmente
                    "billable": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries")
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 1
    assert not post_route.called
    err = capsys.readouterr().err
    assert "campo ausente" in err


@respx.mock
def test_add_tarefa_inexistente_rc1(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _setup_env(monkeypatch)
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u1"}))
    respx.get(f"{BASE}/workspaces/ws1/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Procurement Garage"}])
    )
    respx.get(f"{BASE}/workspaces/ws1/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[])  # sem tarefas no workspace
    )
    respx.get(f"{BASE}/workspaces/ws1/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Atividades Internas"}])
    )
    entries_file = tmp_path / "entries.json"
    entries_file.write_text(
        json.dumps(
            [
                {
                    "description": "Reunião Cliente X",
                    "start": "2026-01-28T13:00:00-03:00",
                    "end": "2026-01-28T14:00:00-03:00",
                    "task_name": "Tarefa Inexistente",
                    "tag_names": ["Atividades Internas"],
                    "billable": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    post_route = respx.post(f"{BASE}/workspaces/ws1/time-entries")
    rc = main(["add", "--file", str(entries_file)])
    assert rc == 1
    assert not post_route.called
    err = capsys.readouterr().err
    assert err.strip()  # alguma mensagem de erro no stderr


@respx.mock
def test_add_dry_run_usa_project_name(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "W")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "")
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u"}))
    respx.get(f"{BASE}/workspaces/W/projects").mock(
        return_value=httpx.Response(
            200, json=[{"id": "p1", "name": "Proj A"}, {"id": "p2", "name": "Proj B"}]
        )
    )
    respx.get(f"{BASE}/workspaces/W/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": "Dup"}])
    )
    respx.get(f"{BASE}/workspaces/W/projects/p2/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t2", "name": "Dup"}])
    )
    respx.get(f"{BASE}/workspaces/W/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "Tag"}])
    )
    item = [
        {
            "description": "x",
            "start": "2026-06-04T09:00:00",
            "end": "2026-06-04T10:00:00",
            "task_name": "Dup",
            "tag_names": ["Tag"],
            "billable": False,
            "project_name": "Proj B",
        }
    ]
    f = tmp_path / "e.json"
    f.write_text(json.dumps(item), encoding="utf-8")
    rc = main(["add", "--file", str(f), "--dry-run"])
    assert rc == 0
    payloads = json.loads(capsys.readouterr().out)
    assert payloads[0]["projectId"] == "p2"
    assert payloads[0]["taskId"] == "t2"
    from clockify_horas.learned import read_learned

    assert read_learned() == []  # dry-run não grava


@respx.mock
def test_add_grava_learned_no_sucesso(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("CLOCKIFY_API_KEY", "k")
    monkeypatch.setenv("CLOCKIFY_WORKSPACE_ID", "W")
    monkeypatch.setenv("OUTLOOK_ICS_URL", "")
    respx.get(f"{BASE}/user").mock(return_value=httpx.Response(200, json={"id": "u"}))
    respx.get(f"{BASE}/workspaces/W/projects").mock(
        return_value=httpx.Response(200, json=[{"id": "p1", "name": "Proj Demo"}])
    )
    respx.get(f"{BASE}/workspaces/W/projects/p1/tasks").mock(
        return_value=httpx.Response(200, json=[{"id": "t1", "name": "T"}])
    )
    respx.get(f"{BASE}/workspaces/W/tags").mock(
        return_value=httpx.Response(200, json=[{"id": "g1", "name": "G"}])
    )
    respx.post(f"{BASE}/workspaces/W/time-entries").mock(
        return_value=httpx.Response(201, json={"id": "e1"})
    )
    item = [
        {
            "description": "Reunião Recorrente",
            "start": "2026-06-04T09:00:00",
            "end": "2026-06-04T10:00:00",
            "task_name": "T",
            "tag_names": ["G"],
            "billable": False,
            "project_name": "Proj Demo",
        }
    ]
    f = tmp_path / "e.json"
    f.write_text(json.dumps(item), encoding="utf-8")
    rc = main(["add", "--file", str(f)])
    assert rc == 0
    from clockify_horas.learned import read_learned

    assert read_learned() == [
        {
            "match": "Reunião Recorrente",
            "project_name": "Proj Demo",
            "task_name": "T",
            "tag_names": ["G"],
            "billable": False,
        }
    ]


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
