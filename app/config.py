from functools import lru_cache
from typing import List

from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., env="TELEGRAM_BOT_TOKEN")
    todoist_api_token: str = Field(..., env="TODOIST_API_TOKEN")
    google_service_account_info: str = Field(..., env="GOOGLE_SERVICE_ACCOUNT_INFO")
    google_calendar_id: str = Field(..., env="GOOGLE_CALENDAR_ID")
    huggingface_api_token: str = Field(..., env="HUGGINGFACE_API_TOKEN")
    huggingface_model: str = Field(
        default="mistralai/Mistral-7B-Instruct-v0.2",
        env="HUGGINGFACE_MODEL",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


@lru_cache()
def get_google_calendar_ids() -> List[str]:
    raw_value = get_settings().google_calendar_id
    return [item.strip() for item in raw_value.split(",") if item.strip()]
