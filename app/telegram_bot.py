import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from .config import Settings, get_google_calendar_ids, get_settings
from .services.google_calendar import GoogleCalendarClient
from .services.llm import HuggingFaceLLMClient
from .services.plan_builder import PlanBuilder
from .services.todoist import TodoistClient

router = APIRouter()

USER_INSTRUCTIONS: Dict[int, str] = {}
USER_LAST_PLANS: Dict[int, str] = {}


async def poll_updates(settings: Settings) -> None:
    offset: Optional[int] = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            try:
                response = await client.get(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/getUpdates",
                    params={"timeout": 30, "offset": offset},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                await asyncio.sleep(5)
                continue

            updates = response.json().get("result", [])
            for update in updates:
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1

                message = update.get("message")
                if message:
                    await dispatch_message(message, settings)


async def send_message(token: str, chat_id: int, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()


def parse_command(message: dict) -> tuple[str, Optional[str]]:
    text = message.get("text", "")
    if not text.startswith("/"):
        return "", None
    parts = text.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else None
    return command, args


async def handle_plan_command(
    *,
    message: dict,
    args: Optional[str],
    settings: Settings,
) -> str:
    user_id = message["from"]["id"]

    todoist_client = TodoistClient(settings.todoist_api_token)
    tasks = [task.to_plan_item() for task in await todoist_client.fetch_tasks()]

    service_account_info = settings.google_service_account_info
    if isinstance(service_account_info, str):
        service_account_info = json.loads(service_account_info)

    calendar_ids = get_google_calendar_ids()
    calendar_client = GoogleCalendarClient(
        service_account_info=service_account_info,
        calendar_ids=calendar_ids,
    )
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    events = [
        event.to_plan_item()
        for event in calendar_client.fetch_events(now, now + timedelta(days=1))
    ]

    instructions = USER_INSTRUCTIONS.get(user_id)
    if args:
        instructions = f"{instructions}. {args}" if instructions else args

    llm_client = HuggingFaceLLMClient(
        api_token=settings.huggingface_api_token,
        model=settings.huggingface_model,
    )
    builder = PlanBuilder(llm_client=llm_client)
    try:
        plan_text = await builder.build_plan(
            now=now,
            tasks=tasks,
            events=events,
            instructions=instructions,
        )
        USER_LAST_PLANS[user_id] = plan_text
        return plan_text
    except (httpx.HTTPError, ValueError) as exc:
        return "Не удалось построить расписание с помощью модели: {0}. Попробуйте еще раз позже.".format(
            str(exc)
        )


async def handle_set_instructions_command(*, message: dict, args: Optional[str]) -> str:
    user_id = message["from"]["id"]
    if not args:
        USER_INSTRUCTIONS.pop(user_id, None)
        return "Инструкции удалены."
    USER_INSTRUCTIONS[user_id] = args
    return "Инструкции сохранены."


async def handle_adjust_plan_command(
    *, message: dict, args: Optional[str], settings: Settings
) -> str:
    user_id = message["from"]["id"]
    if not args:
        return "Опишите, какие правки нужно внести в расписание."

    previous_plan = USER_LAST_PLANS.get(user_id)
    if not previous_plan:
        return "Сначала запросите план командой /plan, а затем повторите попытку."

    llm_client = HuggingFaceLLMClient(
        api_token=settings.huggingface_api_token,
        model=settings.huggingface_model,
    )
    builder = PlanBuilder(llm_client=llm_client)
    instructions = USER_INSTRUCTIONS.get(user_id)

    try:
        updated_plan = await builder.revise_plan(
            previous_plan=previous_plan,
            modifications=args,
            instructions=instructions,
        )
        USER_LAST_PLANS[user_id] = updated_plan
        return updated_plan
    except (httpx.HTTPError, ValueError) as exc:
        return "Не удалось применить правки с помощью модели: {0}. Попробуйте еще раз позже.".format(
            str(exc)
        )


async def dispatch_message(message: dict, settings: Settings) -> None:
    command, args = parse_command(message)
    chat_id = message["chat"]["id"]

    if command == "/plan":
        plan_text = await handle_plan_command(message=message, args=args, settings=settings)
        await send_message(settings.telegram_bot_token, chat_id, plan_text)
    elif command == "/set_instructions":
        response = await handle_set_instructions_command(message=message, args=args)
        await send_message(settings.telegram_bot_token, chat_id, response)
    elif command == "/adjust_plan":
        response = await handle_adjust_plan_command(message=message, args=args, settings=settings)
        await send_message(settings.telegram_bot_token, chat_id, response)
    elif command == "/start":
        await send_message(
            settings.telegram_bot_token,
            chat_id,
            "Привет! Используй /plan чтобы получить план на день."
            " Команда /set_instructions сохраняет общие пожелания,"
            " а /adjust_plan помогает внести правки в уже составленное расписание.",
        )
    else:
        await send_message(
            settings.telegram_bot_token,
            chat_id,
            "Неизвестная команда. Используй /plan или /set_instructions.",
        )


@router.post("/webhook")
async def telegram_webhook(
    payload: dict,
    settings: Settings = Depends(get_settings),
):
    message = payload.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Invalid payload")

    await dispatch_message(message, settings)
    return {"status": "ok"}
