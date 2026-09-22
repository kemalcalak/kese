"""Application settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_prefix="KESE_")

    env: str = "local"
    database_url: str = "postgresql+asyncpg://kese:kese@127.0.0.1:5433/kese"
