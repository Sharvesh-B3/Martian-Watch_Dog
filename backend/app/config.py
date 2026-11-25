"""Environment configuration for the Aegis Watchdog backend."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and a root-level `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # MQTT broker (isolated Docker lab)
    MQTT_HOST: str = "127.0.0.1"
    MQTT_PORT: int = 1883
    MQTT_TOPIC_PREFIX: str = "campus/lab1"

    # LLM provider
    LLM_PROVIDER: Literal["gemini", "local"] = "gemini"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    LOCAL_LLM_BASE_URL: str | None = None
    LOCAL_LLM_MODEL: str = "local-model"
    LLM_TIMEOUT_SECONDS: float = 30.0

    # Persistence
    DB_PATH: str = "backend/data/watchdog.db"

    # Frontend dev origins
    CORS_ORIGINS: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )

    # Detection
    WINDOW_SECONDS: int = 60

    @model_validator(mode="after")
    def validate_llm_settings(self) -> "Settings":
        """Fail fast when the selected LLM provider is not configured."""
        if self.LLM_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        if self.LLM_PROVIDER == "local" and not self.LOCAL_LLM_BASE_URL:
            raise ValueError("LOCAL_LLM_BASE_URL is required when LLM_PROVIDER=local")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()
