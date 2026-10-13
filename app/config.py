"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.constants import DEFAULT_JOB_TTL_SECONDS, DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str
    openrouter_api_key: str
    redis_url: str = "redis://localhost:6379/0"
    job_ttl_seconds: int = DEFAULT_JOB_TTL_SECONDS
    tool_http_timeout_seconds: float = DEFAULT_TOOL_HTTP_TIMEOUT_SECONDS
    # Demo/dev only: allow http://localhost and private hosts for tool endpoints.
    allow_local_tool_endpoints: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
