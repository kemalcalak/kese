"""Database readiness endpoint."""

from fastapi import APIRouter, Request, Response, status
from sqlalchemy.exc import SQLAlchemyError

from kese.core.database import check_connection

router = APIRouter()


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict[str, str]:
    """Report whether the database can execute a query."""
    database_engine = request.app.state.database_engine
    try:
        await check_connection(database_engine)
    except SQLAlchemyError, OSError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable"}

    return {"status": "ready"}
