"""Async SQLAlchemy database infrastructure."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)

from kese.core.settings import Settings


def create_engine(database_url: str | None = None) -> AsyncEngine:
    """Create an async SQLAlchemy engine for the configured database."""
    url = database_url or Settings().database_url
    return create_async_engine(url, pool_pre_ping=True)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a database session for a FastAPI request."""
    session_factory = request.app.state.async_session_factory
    async with session_factory() as session:
        yield session


async def check_connection(database_engine: AsyncEngine) -> None:
    """Execute a lightweight query to verify database connectivity."""
    async with database_engine.connect() as connection:
        await connection.execute(text("SELECT 1"))
