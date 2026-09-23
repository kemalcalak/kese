"""Report HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.schemas.reports import MonthlyReport, TrendPoint
from kese.services.reports import get_monthly_report, get_trend

router = APIRouter(prefix="/reports", tags=["reports"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]


def invalid_request(error: ValueError) -> HTTPException:
    """Translate report parameter errors into a validation response."""
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)
    )


@router.get("/monthly", response_model=MonthlyReport)
async def monthly_report(
    session: Session,
    user: CurrentUser,
    month: str = Query(...),
    currency: str = Query(..., min_length=3, max_length=3),
) -> MonthlyReport:
    """Return the caller's report for one UTC calendar month."""
    try:
        return await get_monthly_report(session, user.id, month, currency)
    except ValueError as error:
        raise invalid_request(error) from error


@router.get("/trend", response_model=list[TrendPoint])
async def trend_report(
    session: Session,
    user: CurrentUser,
    until: str = Query(...),
    months: int = Query(..., ge=1, le=120),
    currency: str = Query(..., min_length=3, max_length=3),
) -> list[TrendPoint]:
    """Return the caller's month trend ending at until."""
    try:
        return await get_trend(session, user.id, until, months, currency)
    except ValueError as error:
        raise invalid_request(error) from error
