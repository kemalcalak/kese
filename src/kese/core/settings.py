"""Application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KESE_")

    env: str = "local"
    database_url: str = "postgresql+asyncpg://kese:kese@127.0.0.1:5433/kese"
    jwt_secret: str = ""
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    events_idle_seconds: float = 25.0
    login_rate_limit: str = "10/minute"
