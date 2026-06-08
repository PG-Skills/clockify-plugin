import resolve


class FakeCl:
    """Substitui o módulo clockify nos testes (mesma assinatura)."""

    def __init__(self, projects=None, tasks=None, tags=None, existing=None):
        self._projects = projects or {}
        self._tasks = tasks or {}
        self._tags = tags or {}
        self.existing = existing or []
        self.created = []

    def search_projects(self, k, ws, name):
        return self._projects.get(name, [])

    def tasks_in_project(self, k, ws, pid, name):
        return self._tasks.get((pid, name), [])

    def search_tags(self, k, ws, name):
        return self._tags.get(name, [])

    def entries(self, k, ws, uid, start, end):
        return self.existing

    def create_entry(self, k, ws, payload):
        self.created.append(payload)
        return {"id": f"e{len(self.created)}"}


def test_resolve_requires_project(monkeypatch):
    monkeypatch.setattr(resolve, "cl", FakeCl())
    out = resolve.resolve_activity("K", "ws", name="Daily", project=None)
    assert out["status"] == "AMBIGUO" and out["motivo"] == "projeto necessário"


def test_resolve_ok(monkeypatch):
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )
    monkeypatch.setattr(resolve, "cl", fake)
    out = resolve.resolve_activity("K", "ws", name="Dev", project="Proj X")
    assert out == {"status": "OK", "project_id": "p1", "task_id": "t1", "tag_ids": []}


def test_resolve_ambiguous_project_returns_candidates(monkeypatch):
    fake = FakeCl(
        projects={"P": [{"id": "p1", "name": "P1"}, {"id": "p2", "name": "P2"}]}
    )
    monkeypatch.setattr(resolve, "cl", fake)
    out = resolve.resolve_activity("K", "ws", name="Dev", project="P")
    assert out["status"] == "AMBIGUO" and [c["name"] for c in out["candidatos"]] == [
        "P1",
        "P2",
    ]


def test_add_entries_skips_duplicates(monkeypatch):
    # já existe um entry no dia 2026-01-28 para task t1
    existing = [{"taskId": "t1", "timeInterval": {"start": "2026-01-28T12:00:00Z"}}]
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
        existing=existing,
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [
        {
            "description": "d",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Proj X",
        }
    ]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert out["gravados"] == 0 and out["pulados_duplicata"] == 1 and fake.created == []


def test_add_entries_same_task_multiple_blocks_all_written(monkeypatch):
    # 3 blocos da MESMA tarefa no mesmo dia (starts distintos) -> todos gravam, nada pulado
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [
        {
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Proj X",
        },
        {
            "date": "2026-01-28",
            "start": "11:00",
            "end": "12:00",
            "task": "Dev",
            "project": "Proj X",
        },
        {
            "date": "2026-01-28",
            "start": "13:00",
            "end": "18:00",
            "task": "Dev",
            "project": "Proj X",
        },
    ]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert out["gravados"] == 3 and out["pulados_duplicata"] == 0
    assert len(fake.created) == 3


def test_add_entries_skips_only_exact_same_start(monkeypatch):
    # já existe um bloco às 09:00 (=12:00Z): re-logar 09:00 pula; 11:00 (mesma tarefa) grava
    existing = [{"taskId": "t1", "timeInterval": {"start": "2026-01-28T12:00:00Z"}}]
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},
        existing=existing,
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [
        {
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Proj X",
        },
        {
            "date": "2026-01-28",
            "start": "11:00",
            "end": "12:00",
            "task": "Dev",
            "project": "Proj X",
        },
    ]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert out["gravados"] == 1 and out["pulados_duplicata"] == 1
    assert len(fake.created) == 1


def test_local_dt_accepts_unpadded_hour():
    from zoneinfo import ZoneInfo

    dt = resolve._local_dt("2026-01-28", "9:00")  # hora sem zero à esquerda
    assert (dt.hour, dt.minute) == (9, 0)
    assert dt.tzinfo == ZoneInfo("America/Sao_Paulo")


def test_add_entries_writes_and_stops_on_error(monkeypatch):
    fake = FakeCl(
        projects={"Proj X": [{"id": "p1", "name": "Proj X"}]},
        tasks={("p1", "Dev"): [{"id": "t1", "name": "Dev"}]},  # "Outra" não existe
    )
    monkeypatch.setattr(resolve, "cl", fake)
    items = [
        {
            "description": "d1",
            "date": "2026-01-28",
            "start": "09:00",
            "end": "10:00",
            "task": "Dev",
            "project": "Proj X",
        },
        {
            "description": "d2",
            "date": "2026-01-28",
            "start": "10:00",
            "end": "11:00",
            "task": "Outra",
            "project": "Proj X",
        },
    ]
    out = resolve.add_entries("K", "ws", "u1", items)
    assert (
        out["gravados"] == 1
        and out["falhou_em"] == 1
        and out["motivo"] == "tarefa não encontrada"
    )
    assert len(fake.created) == 1
