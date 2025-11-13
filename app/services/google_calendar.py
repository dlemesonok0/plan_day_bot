from datetime import datetime, timezone
from typing import Iterable, List

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


def _parse_datetime(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class CalendarEvent:
    def __init__(self, *, event_id: str, summary: str, start: datetime, end: datetime):
        self.event_id = event_id
        self.summary = summary
        self.start = start
        self.end = end

    def to_plan_item(self) -> dict:
        return {
            "type": "event",
            "id": self.event_id,
            "title": self.summary,
            "start": self.start,
            "end": self.end,
        }


class GoogleCalendarClient:
    def __init__(self, *, service_account_info, calendar_ids: Iterable[str]):
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        self.service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        self.calendar_ids = [calendar_id for calendar_id in calendar_ids if calendar_id]
        if not self.calendar_ids:
            raise ValueError("At least one Google Calendar ID must be configured")

    def fetch_events(self, time_min: datetime, time_max: datetime) -> List[CalendarEvent]:
        events: List[CalendarEvent] = []
        for calendar_id in self.calendar_ids:
            try:
                events_result = (
                    self.service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=time_min.astimezone(timezone.utc).isoformat(),
                        timeMax=time_max.astimezone(timezone.utc).isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
            except HttpError as error:
                if error.resp.status == 404:
                    # Skip calendars that are not found or inaccessible instead of
                    # propagating the error and crashing the bot.
                    continue
                raise
            for item in events_result.get("items", []):
                start_info = item.get("start", {})
                end_info = item.get("end", {})
                start_str = start_info.get("dateTime") or start_info.get("date")
                end_str = end_info.get("dateTime") or end_info.get("date")
                if not start_str or not end_str:
                    continue
                if len(start_str) == 10:
                    start_str += "T00:00:00+00:00"
                if len(end_str) == 10:
                    end_str += "T23:59:00+00:00"
                start = _parse_datetime(start_str)
                end = _parse_datetime(end_str)
                events.append(
                    CalendarEvent(
                        event_id=item.get("id", ""),
                        summary=item.get("summary", "Без названия"),
                        start=start,
                        end=end,
                    )
                )
        return sorted(events, key=lambda event: event.start)
