from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CalEvent:
    """Evento de calendário lido do ICS."""

    title: str
    start: datetime
    end: datetime


@dataclass
class TimeEntry:
    """Um lançamento de tempo a ser criado no Clockify (horários em hora local)."""

    description: str
    start: datetime
    end: datetime
    task_name: str
    tag_names: list[str]
    billable: bool


@dataclass
class Metadata:
    """IDs do workspace Clockify, indexados por nome para resolução.

    - projects: nome do projeto -> projectId
    - tasks: (projectId, nome da tarefa) -> taskId
    - tags: nome da tag -> tagId
    """

    workspace_id: str
    user_id: str
    projects: dict[str, str] = field(default_factory=dict)
    tasks: dict[tuple[str, str], str] = field(default_factory=dict)
    tags: dict[str, str] = field(default_factory=dict)
