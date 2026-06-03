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
