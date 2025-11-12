from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .llm import HuggingFaceLLMClient


@dataclass
class PlanSourceItem:
    title: str
    start: Optional[datetime]
    end: Optional[datetime]
    item_type: str


class PlanBuilder:
    def __init__(self, *, llm_client: HuggingFaceLLMClient):
        self._llm_client = llm_client

    async def build_plan(
        self,
        *,
        now: datetime,
        tasks: Iterable[dict],
        events: Iterable[dict],
        instructions: Optional[str],
    ) -> str:
        items: List[PlanSourceItem] = []
        for event in events:
            items.append(
                PlanSourceItem(
                    title=event.get("title", "Без названия"),
                    start=event.get("start"),
                    end=event.get("end"),
                    item_type="event",
                )
            )
        for task in tasks:
            items.append(
                PlanSourceItem(
                    title=task.get("title", "Без названия"),
                    start=task.get("start"),
                    end=None,
                    item_type="task",
                )
            )

        tzinfo = self._detect_timezone(items, fallback=now.tzinfo or timezone.utc)
        prompt = self._build_prompt(
            now=now,
            timezone_info=tzinfo,
            tasks=[item for item in items if item.item_type == "task"],
            events=[item for item in items if item.item_type == "event"],
            instructions=instructions,
        )

        plan_text = await self._llm_client.generate(prompt)
        return plan_text

    async def revise_plan(
        self,
        *,
        previous_plan: str,
        modifications: str,
        instructions: Optional[str],
    ) -> str:
        instructions_block = instructions.strip() if instructions else "нет"
        prompt = f"""
Ты — персональный ассистент по тайм-менеджменту. Тебе передано расписание на день, составленное в формате тайм-блокинга. Нужно внести правки и вернуть обновлённый план, следуя правилам:
- Всегда придерживайся формата `HH:MM–HH:MM — описание блока` и сортировки по времени.
- Сохраняй события из исходного плана, если изменения их не отменяют.
- Учитывай взаимное расположение блоков, дедлайны и персональные пожелания.
- В конце добавь блок "Итоги дня".

Текущее расписание:
{previous_plan}

Пожелания пользователя: {modifications.strip()}.
Постоянные инструкции пользователя: {instructions_block}.

Верни только обновлённое расписание без дополнительных пояснений.
"""

        revised_plan = await self._llm_client.generate(prompt.strip())
        return revised_plan

    def _detect_timezone(self, items: Iterable[PlanSourceItem], fallback: timezone) -> timezone:
        for item in items:
            if item.start and item.start.tzinfo:
                return item.start.tzinfo
            if item.end and item.end.tzinfo:
                return item.end.tzinfo
        return fallback

    def _format_datetime(self, value: Optional[datetime], tzinfo: timezone) -> str:
        if not value:
            return "не указано"
        local_dt = value.astimezone(tzinfo)
        tz_name = tzinfo.tzname(local_dt) if hasattr(tzinfo, "tzname") else None
        tz_suffix = f" ({tz_name})" if tz_name else ""
        return f"{local_dt.strftime('%Y-%m-%d %H:%M')}{tz_suffix}"

    def _build_prompt(
        self,
        *,
        now: datetime,
        timezone_info: timezone,
        tasks: List[PlanSourceItem],
        events: List[PlanSourceItem],
        instructions: Optional[str],
    ) -> str:
        now_local = now.astimezone(timezone_info)
        tz_name = timezone_info.tzname(now_local) if hasattr(timezone_info, "tzname") else None
        tz_label = tz_name or "local time"

        event_lines: List[str] = []
        for event in events:
            start_str = self._format_datetime(event.start, timezone_info)
            end_str = self._format_datetime(event.end, timezone_info)
            event_lines.append(f"- {event.title} (с {start_str} до {end_str})")
        events_block = "\n".join(event_lines) if event_lines else "- событий нет"

        task_lines: List[str] = []
        for idx, task in enumerate(tasks, start=1):
            due_str = self._format_datetime(task.start, timezone_info)
            task_lines.append(f"{idx}. {task.title} (желательно завершить к {due_str})")
        tasks_block = "\n".join(task_lines) if task_lines else "1. Нет задач, но добавь полезные привычки"

        instructions_block = instructions.strip() if instructions else "нет"

        prompt = f"""
Ты — персональный ассистент по тайм-менеджменту. Составь подробное расписание на один день на русском языке, используя метод тайм-блокинга. Пожалуйста, следуй правилам:
- Всегда используй локальное время ({tz_label}) и формат `HH:MM–HH:MM — описание блока`.
- Объедини события календаря и задачи, равномерно распределяя их по дню. Учитывай дедлайны.
- Добавь необходимые ежедневные рутины: подъем, завтрак, обед, ужин, отдых, подготовку ко сну.
- Если есть свободные окна, заполни их полезными делами или восстановлением.
- В конце добавь короткий блок "Итоги дня" с напоминанием про главное.

Текущее время: {now_local.strftime('%Y-%m-%d %H:%M')} ({tz_label}).

События календаря на сегодня и завтра:
{events_block}

Задачи:
{tasks_block}

Дополнительные инструкции пользователя: {instructions_block}.

Сформируй только расписание без дополнительных пояснений.
"""
        return prompt.strip()
