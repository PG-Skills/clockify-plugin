import json

import httpx
import respx

from clockify_horas.cli import main
from clockify_horas.config import config_path

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
            "Equipe Demo",
            "--tag",
            "Etiqueta Demo",
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
        "task_name": "Equipe Demo",
        "tag_name": "Etiqueta Demo",
        "billable": False,
        "daily_target_hours": 8.0,
    }

    rc = main(["config", "set", "--task", "Outra Tarefa"])
    assert rc == 0
    data = json.loads(config_path().read_text(encoding="utf-8"))
    assert data["defaults"]["task_name"] == "Outra Tarefa"
    assert data["clockify"]["api_key"] == "K"  # preservado


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


def test_config_add_override(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    rc = main(
        [
            "config",
            "add-override",
            "--match",
            "Cliente Demo",
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
            "match": "Cliente Demo",
            "task_name": "Assinatura",
            "tag_name": "Implantação",
            "billable": True,
        }
    ]


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


@respx.mock
def test_config_doctor_workspace_nao_encontrado(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    for var in ("CLOCKIFY_API_KEY", "CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    _seed_config()
    respx.get(f"{BASE}/workspaces").mock(return_value=httpx.Response(200, json=[{"id": "OUTRO"}]))
    rc = main(["config", "doctor"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAIL" in out
    assert "não está entre" in out


@respx.mock
def test_workspaces_lista(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CLOCKIFY_API_KEY", "K")
    for var in ("CLOCKIFY_WORKSPACE_ID", "OUTLOOK_ICS_URL"):
        monkeypatch.delenv(var, raising=False)
    respx.get(f"{BASE}/workspaces").mock(
        return_value=httpx.Response(
            200, json=[{"id": "W1", "name": "Um"}, {"id": "W2", "name": "Dois"}]
        )
    )
    rc = main(["workspaces"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out == [{"id": "W1", "name": "Um"}, {"id": "W2", "name": "Dois"}]
