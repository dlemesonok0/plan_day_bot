from datetime import datetime, timezone
from typing import List, Optional

import httpx


def _parse_datetime(value: str) -> Optional[datetime]:
    value = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class TodoistTask:
    def __init__(self, *, id: str, content: str, due_datetime: Optional[datetime]):
        self.id = id
        self.content = content
        self.due_datetime = due_datetime

    def to_plan_item(self) -> dict:
        return {
            "type": "task",
            "id": self.id,
            "title": self.content,
            "start": self.due_datetime,
        }


class TodoistClient:
    API_URL = "https://api.todoist.com/rest/v2/tasks"

    def __init__(self, token: str):
        self._token = token

    async def fetch_tasks(self) -> List[TodoistTask]:
        headers = {
            "Authorization": f"Bearer {self._token}",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(self.API_URL, headers=headers)
            response.raise_for_status()
            data = response.json()

        tasks: List[TodoistTask] = []
        for item in data:
            due = item.get("due") or {}
            due_datetime: Optional[datetime] = None
            if due:
                due_string = due.get("datetime") or due.get("date")
                if due_string:
                    due_datetime = _parse_datetime(due_string)
            tasks.append(
                TodoistTask(
                    id=str(item["id"]),
                    content=item.get("content", "Без названия"),
                    due_datetime=due_datetime,
                )
            )
        return tasks
