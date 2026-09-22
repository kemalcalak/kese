"""FastAPI application factory."""

from fastapi import FastAPI

from kese.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(title="kese")
    app.include_router(health_router)
    return app


app = create_app()
