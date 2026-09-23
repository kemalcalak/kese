"""FastAPI application factory and cross-cutting HTTP hardening."""

from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from json import dumps
from logging import Formatter, StreamHandler, getLogger
from os import environ
from sys import stdout
from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from kese.api.accounts import router as accounts_router
from kese.api.auth import router as auth_router
from kese.api.budgets import router as budgets_router
from kese.api.categories import router as categories_router
from kese.api.exchange_rates import router as exchange_rates_router
from kese.api.exports import router as exports_router
from kese.api.health import router as health_router
from kese.api.ready import router as ready_router
from kese.api.reports import router as reports_router
from kese.api.statements import router as statements_router
from kese.core.database import create_engine
from kese.core.settings import Settings

access_logger = getLogger("kese.access")
_STATUS_CODES = {
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}


def _configure_access_logger() -> None:
    """Send access logs to stdout without adding duplicate handlers."""
    if any(handler.name == "kese.stdout" for handler in access_logger.handlers):
        return

    handler = StreamHandler(stdout)
    handler.set_name("kese.stdout")
    handler.setFormatter(Formatter("%(message)s"))
    access_logger.addHandler(handler)
    access_logger.setLevel("INFO")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release the application's database engine on shutdown."""
    yield
    database_engine: AsyncEngine = app.state.database_engine
    await database_engine.dispose()


def _request_id(request: Request) -> str:
    """Return the request id assigned by the request middleware."""
    return getattr(request.state, "request_id", str(uuid4()))


def _error_response(
    request: Request,
    status_code: int,
    message: str,
    details: Any = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Build the single public error representation."""
    error: dict[str, Any] = {
        "code": _STATUS_CODES.get(status_code, "internal_error"),
        "message": message,
        "request_id": _request_id(request),
    }
    if details is not None:
        error["details"] = jsonable_encoder(details)
    return JSONResponse(
        status_code=status_code, content={"error": error}, headers=headers
    )


def _login_limit(value: str) -> tuple[int, float]:
    """Parse a simple ``count/window`` rate-limit setting."""
    count_text, period = value.split("/", 1)
    count = int(count_text)
    seconds = {"second": 1.0, "minute": 60.0, "hour": 3600.0}[period.rstrip("s")]
    return count, seconds


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    _configure_access_logger()
    settings = Settings()
    if settings.env != "local" and "KESE_JWT_SECRET" not in environ:
        raise RuntimeError("create_app() requires KESE_JWT_SECRET outside local")

    app = FastAPI(title="kese", lifespan=lifespan)
    database_engine = create_engine(settings.database_url)
    app.state.settings = settings
    app.state.database_engine = database_engine
    app.state.async_session_factory = async_sessionmaker(
        database_engine, expire_on_commit=False
    )
    app.state.login_attempts = defaultdict(deque)
    app.state.login_limit = _login_limit(settings.login_rate_limit)

    @app.middleware("http")
    async def request_hardening(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        started = monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            status_code = response.status_code if response is not None else 500
            duration_ms = (monotonic() - started) * 1000
            access_logger.info(
                dumps(
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "duration_ms": duration_ms,
                        "request_id": request_id,
                    },
                    separators=(",", ":"),
                )
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_response(request, exc.status_code, message, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Validation failed",
            exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        del exc
        response = _error_response(
            request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error"
        )
        response.headers["X-Request-ID"] = _request_id(request)
        return response

    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(budgets_router)
    app.include_router(categories_router)
    app.include_router(exchange_rates_router)
    app.include_router(exports_router)
    app.include_router(health_router)
    app.include_router(reports_router)
    app.include_router(ready_router)
    app.include_router(statements_router)
    return app


app = create_app()
