"""Async SQLAlchemy database infrastructure."""

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kese.core.settings import Settings


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the configured database."""
    url = database_url or Settings().database_url
    return create_async_engine(url, pool_pre_ping=True)


engine = create_engine()
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a database session for a FastAPI request."""
    async with async_session_factory() as session:
        yield session


async def check_connection(database_engine: AsyncEngine) -> None:
    """Execute a lightweight query to verify database connectivity."""
    async with database_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
