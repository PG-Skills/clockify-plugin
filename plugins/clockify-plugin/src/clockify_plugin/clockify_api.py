from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from clockify_plugin.models import Metadata

BASE_URL = "https://api.clockify.me/api/v1"
_PAGE_SIZE = 200


class ClockifyClient:
    """Wrapper fino sobre a API REST do Clockify. Toda chamada HTTP fica aqui."""

    def __init__(self, api_key: str, workspace_id: str, base_url: str = BASE_URL) -> None:
        self.workspace_id = workspace_id
        self._client = httpx.Client(
            base_url=base_url,
            headers={"X-Api-Key": api_key},
            timeout=30.0,
        )

    def _get(self, path: str, **kwargs: Any) -> Any:
        resp = self._client.get(path, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _get_all(self, path: str) -> list[dict[str, Any]]:
        """GET paginado: percorre páginas até vir uma página incompleta."""
        items: list[dict[str, Any]] = []
        page = 1
        while True:
            batch = self._get(path, params={"page": page, "page-size": _PAGE_SIZE})
            items.extend(batch)
            if len(batch) < _PAGE_SIZE:
                return items
            page += 1

    def get_user_id(self) -> str:
        return self._get("/user")["id"]

    def list_workspaces(self) -> list[dict[str, Any]]:
        return self._get("/workspaces")

    def get_metadata(self) -> Metadata:
        ws = self.workspace_id
        user_id = self.get_user_id()
        projects_raw = self._get_all(f"/workspaces/{ws}/projects")
        projects = {p["name"]: p["id"] for p in projects_raw}
        tasks: dict[tuple[str, str], str] = {}
        for p in projects_raw:
            for t in self._get_all(f"/workspaces/{ws}/projects/{p['id']}/tasks"):
                tasks[(p["id"], t["name"])] = t["id"]
        tags = {g["name"]: g["id"] for g in self._get_all(f"/workspaces/{ws}/tags")}
        return Metadata(
            workspace_id=ws,
            user_id=user_id,
            projects=projects,
            tasks=tasks,
            tags=tags,
        )

    def get_entries_for_date(
        self, user_id: str, target_date: date, tz: ZoneInfo
    ) -> list[dict[str, Any]]:
        """Lançamentos do usuário no dia local (para checagem anti-duplicata).

        A janela é o dia local convertido para instantes UTC — evitando o erro de
        tratar 00:00–23:59 local como se fosse UTC (que em UTC-3 perderia 3h do dia).
        """
        day_start = datetime.combine(target_date, time.min, tzinfo=tz).astimezone(UTC)
        day_end = day_start + timedelta(days=1)
        return self._get(
            f"/workspaces/{self.workspace_id}/user/{user_id}/time-entries",
            params={
                "start": day_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": day_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

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

    def create_entry(self, payload: dict[str, Any]) -> dict[str, Any]:
        resp = self._client.post(f"/workspaces/{self.workspace_id}/time-entries", json=payload)
        resp.raise_for_status()
        return resp.json()
