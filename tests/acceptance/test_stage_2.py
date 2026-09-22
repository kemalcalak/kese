"""Stage 2 - the database.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up (`docker compose up -d`) and the
migrations applied.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from kese.core.settings import Settings
from kese.main import create_app


def test_settings_carry_an_async_database_url() -> None:
    assert Settings().database_url.startswith("postgresql+asyncpg://")


def test_ready_reports_a_reachable_database() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_ready_reports_an_unreachable_database(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "KESE_DATABASE_URL", "postgresql+asyncpg://kese:kese@127.0.0.1:5999/kese"
    )

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.get("/ready")

    assert response.status_code == 503


def test_the_session_dependency_is_an_async_generator() -> None:
    from kese.core.database import get_session

    assert inspect.isasyncgenfunction(get_session)


def test_the_users_table_exists_after_the_migrations() -> None:
    async def users_table() -> str | None:
        engine = create_async_engine(Settings().database_url)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text("select to_regclass('public.users')")
                )
                return result.scalar()
        finally:
            await engine.dispose()

    assert asyncio.run(users_table()) == "users"
