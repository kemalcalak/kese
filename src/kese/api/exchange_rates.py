"""Exchange-rate and conversion HTTP endpoints."""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.schemas.exchange_rate import ConversionResponse, ExchangeRateResponse
from kese.services.exchange_rates import (
    BulletinUnavailableError,
    CurrencyNotFoundError,
    convert,
    get_rate,
)

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]
QueryDate = Annotated[date, Query(...)]
Amount = Annotated[Decimal, Query(...)]
CurrencyCode = Annotated[str, Query(min_length=3, max_length=3)]


@router.get("/rates/{code}", response_model=ExchangeRateResponse)
async def rate_endpoint(
    request: Request,
    session: Session,
    user: CurrentUser,
    code: str,
    on: QueryDate,
) -> ExchangeRateResponse:
    """Return the TCMB selling rate for a currency and date."""
    del user
    try:
        cached_rate = await get_rate(session, code, on, request.app.state.settings)
    except CurrencyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except BulletinUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE) from error
    return ExchangeRateResponse(
        code=code.upper(), on=on, rate_date=cached_rate.rate_date, rate=cached_rate.rate
    )


@router.get("/convert", response_model=ConversionResponse)
async def convert_endpoint(
    request: Request,
    session: Session,
    user: CurrentUser,
    amount: Amount,
    source: CurrencyCode,
    target: CurrencyCode,
    on: QueryDate,
) -> ConversionResponse:
    """Convert an amount through TRY using TCMB selling rates."""
    del user
    try:
        converted_amount, rate, converted = await convert(
            session,
            amount,
            source,
            target,
            on,
            request.app.state.settings,
        )
    except CurrencyNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from error
    except BulletinUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE) from error
    return ConversionResponse(amount=converted_amount, rate=rate, converted=converted)
