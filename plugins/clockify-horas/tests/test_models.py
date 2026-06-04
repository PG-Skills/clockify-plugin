from datetime import datetime

from clockify_horas.models import CalEvent, Metadata, TimeEntry


def test_calevent_guarda_titulo_e_intervalo():
    ev = CalEvent(
        title="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0),
        end=datetime(2026, 1, 28, 14, 0),
    )
    assert ev.title == "Reunião Cliente X"
    assert ev.end > ev.start


def test_timeentry_tem_campos_obrigatorios():
    entry = TimeEntry(
        description="Ajustes agente Spend Analysis",
        start=datetime(2026, 1, 28, 13, 0),
        end=datetime(2026, 1, 28, 16, 0),
        task_name=".Célula de Inovação: Time IA",
        tag_names=["Atividades Internas"],
        billable=False,
    )
    assert entry.task_name == ".Célula de Inovação: Time IA"
    assert entry.tag_names == ["Atividades Internas"]
    assert entry.billable is False


def test_metadata_resolve_nomes():
    md = Metadata(
        workspace_id="ws1",
        user_id="u1",
        projects={"Procurement Garage": "p1"},
        tasks={("p1", ".Célula de Inovação: Time IA"): "t1"},
        tags={"Atividades Internas": "g1"},
    )
    assert md.projects["Procurement Garage"] == "p1"
    assert md.tasks[("p1", ".Célula de Inovação: Time IA")] == "t1"
    assert md.tags["Atividades Internas"] == "g1"
