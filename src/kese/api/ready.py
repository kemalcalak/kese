"""Database readiness endpoint."""

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy.exc import SQLAlchemyError

from kese.core.database import check_connection

router = APIRouter()


@router.get("/ready")
async def ready(request: Request) -> dict[str, str]:
    """Report whether the database can execute a query."""
    database_engine = request.app.state.database_engine
    try:
        await check_connection(database_engine)
    except (SQLAlchemyError, OSError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE) from error

    return {"status": "ready"}
