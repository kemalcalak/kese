"""Application settings."""

import secrets

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KESE_")

    env: str = "local"
    database_url: str = "postgresql+asyncpg://kese:kese@127.0.0.1:5433/kese"
    jwt_secret: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    events_idle_seconds: float = 25.0
    login_rate_limit: str = "10/minute"

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        """Require a usable JWT secret in every environment."""
        if len(value.strip()) < 32:
            raise ValueError("KESE_JWT_SECRET must be at least 32 characters")
        return value
