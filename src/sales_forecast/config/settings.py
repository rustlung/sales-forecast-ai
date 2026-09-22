from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(min_length=1)
    log_level: str = "INFO"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
