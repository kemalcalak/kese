"""FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kese.api.accounts import router as accounts_router
from kese.api.auth import router as auth_router
from kese.api.budgets import router as budgets_router
from kese.api.categories import router as categories_router
from kese.api.exchange_rates import router as exchange_rates_router
from kese.api.health import router as health_router
from kese.api.ready import router as ready_router
from kese.api.statements import router as statements_router
from kese.core.database import create_engine
from kese.core.settings import Settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release the application's database engine on shutdown."""
    yield
    database_engine: AsyncEngine = app.state.database_engine
    await database_engine.dispose()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="kese", lifespan=lifespan)
    settings = Settings()
    database_engine = create_engine(settings.database_url)
    app.state.settings = settings
    app.state.database_engine = database_engine
    app.state.async_session_factory = async_sessionmaker(
        database_engine, expire_on_commit=False
    )
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(budgets_router)
    app.include_router(categories_router)
    app.include_router(exchange_rates_router)
    app.include_router(health_router)
    app.include_router(ready_router)
    app.include_router(statements_router)

    return app


app = create_app()
