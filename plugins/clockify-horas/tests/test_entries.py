from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from clockify_horas.config import Defaults
from clockify_horas.entries import (
    build_payload,
    day_total_hours,
    from_event,
    target_warning,
    to_utc_iso,
)
from clockify_horas.models import CalEvent, Metadata, TimeEntry

TZ = ZoneInfo("America/Sao_Paulo")

DEFAULTS = Defaults(
    task_name=".Etiqueta Demo: Equipe Demo",
    tag_name="Atividades Internas",
    billable=False,
    daily_target_hours=8.0,
)

META = Metadata(
    workspace_id="ws1",
    user_id="u1",
    projects={"Procurement Garage": "p1"},
    tasks={("p1", ".Etiqueta Demo: Equipe Demo"): "t1"},
    tags={"Atividades Internas": "g1"},
)


def test_from_event_aplica_defaults():
    ev = CalEvent(
        title="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0, tzinfo=TZ),
        end=datetime(2026, 1, 28, 14, 0, tzinfo=TZ),
    )
    entry = from_event(ev, DEFAULTS)
    assert entry.description == "Reunião Cliente X"
    assert entry.task_name == ".Etiqueta Demo: Equipe Demo"
    assert entry.tag_names == ["Atividades Internas"]
    assert entry.billable is False
    assert entry.start == ev.start


def test_day_total_hours_soma_duracoes():
    entries = [
        TimeEntry(
            "a",
            datetime(2026, 1, 28, 9),
            datetime(2026, 1, 28, 11),
            ".Etiqueta Demo: Equipe Demo",
            ["t"],
            False,
        ),
        TimeEntry(
            "b",
            datetime(2026, 1, 28, 13),
            datetime(2026, 1, 28, 16),
            ".Etiqueta Demo: Equipe Demo",
            ["t"],
            False,
        ),
    ]
    assert day_total_hours(entries) == 5.0


def test_target_warning_avisa_quando_abaixo():
    msg = target_warning(total=5.0, target=8.0)
    assert msg is not None
    assert "5" in msg and "8" in msg


def test_target_warning_silencia_quando_no_alvo():
    assert target_warning(total=8.0, target=8.0) is None
    assert target_warning(total=7.75, target=8.0) is None  # tolerância de 15min


def test_to_utc_iso_converte_local_para_utc():
    dt = datetime(2026, 1, 28, 13, 0, tzinfo=TZ)  # UTC-3
    assert to_utc_iso(dt) == "2026-01-28T16:00:00Z"


def _entry() -> TimeEntry:
    return TimeEntry(
        description="Reunião Cliente X",
        start=datetime(2026, 1, 28, 13, 0, tzinfo=TZ),
        end=datetime(2026, 1, 28, 14, 0, tzinfo=TZ),
        task_name=".Etiqueta Demo: Equipe Demo",
        tag_names=["Atividades Internas"],
        billable=False,
    )


def test_build_payload_resolve_ids_e_converte_utc():
    payload = build_payload(_entry(), META)
    assert payload == {
        "start": "2026-01-28T16:00:00Z",
        "end": "2026-01-28T17:00:00Z",
        "description": "Reunião Cliente X",
        "projectId": "p1",
        "taskId": "t1",
        "tagIds": ["g1"],
        "billable": False,
    }


def test_build_payload_tarefa_inexistente_levanta():
    entry = _entry()
    entry.task_name = "Tarefa Que Não Existe"
    with pytest.raises(KeyError, match="Tarefa Que Não Existe"):
        build_payload(entry, META)


def test_build_payload_tag_inexistente_levanta():
    entry = _entry()
    entry.tag_names = ["Tag Inexistente"]
    with pytest.raises(KeyError, match="Tag Inexistente"):
        build_payload(entry, META)


def test_build_payload_tarefa_ambigua_levanta():
    """Tarefa com mesmo nome em dois projetos deve levantar KeyError com 'ambígua'."""
    meta_dup = Metadata(
        workspace_id="ws1",
        user_id="u1",
        projects={"Proj A": "p1", "Proj B": "p2"},
        tasks={("p1", "Dup"): "t1", ("p2", "Dup"): "t2"},
        tags={"Atividades Internas": "g1"},
    )
    entry = TimeEntry(
        description="Teste",
        start=datetime(2026, 1, 28, 13, 0, tzinfo=TZ),
        end=datetime(2026, 1, 28, 14, 0, tzinfo=TZ),
        task_name="Dup",
        tag_names=["Atividades Internas"],
        billable=False,
    )
    with pytest.raises(KeyError, match="ambígua"):
        build_payload(entry, meta_dup)


def test_build_payload_tarefa_unica_resolve():
    """Nome único deve continuar resolvendo normalmente."""
    payload = build_payload(_entry(), META)
    assert payload["projectId"] == "p1"
    assert payload["taskId"] == "t1"
