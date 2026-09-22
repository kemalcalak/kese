"""FastAPI application factory."""

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine

from kese.api.health import router as health_router
from kese.api.ready import router as ready_router
from kese.core.database import create_engine
from kese.core.settings import Settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="kese")
    app.state.database_engine = create_engine(Settings().database_url)
    app.include_router(health_router)
    app.include_router(ready_router)

    @app.on_event("shutdown")
    async def close_database() -> None:
        """Release the application's database engine."""
        database_engine: AsyncEngine = app.state.database_engine
        await database_engine.dispose()

    return app


app = create_app()
