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
