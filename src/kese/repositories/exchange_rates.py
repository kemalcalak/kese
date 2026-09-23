"""Database queries for cached exchange rates."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import ExchangeRate


async def find_cached_rate(
    session: AsyncSession, currency_code: str, requested_date: date
) -> ExchangeRate | None:
    """Find a cached response for exactly the requested date."""
    result = await session.execute(
        select(ExchangeRate).where(
            ExchangeRate.currency_code == currency_code,
            ExchangeRate.requested_date == requested_date,
        )
    )
    return result.scalar_one_or_none()


async def save_rates(
    session: AsyncSession,
    requested_date: date,
    rate_date: date,
    rates: dict[str, Decimal],
) -> None:
    """Insert bulletin rates for the requested date, preserving cache entries."""
    for currency_code, rate in rates.items():
        existing = await session.scalar(
            select(ExchangeRate).where(
                ExchangeRate.currency_code == currency_code,
                ExchangeRate.requested_date == requested_date,
            )
        )
        if existing is None:
            session.add(
                ExchangeRate(
                    currency_code=currency_code,
                    requested_date=requested_date,
                    rate_date=rate_date,
                    rate=rate,
                )
            )
    await session.commit()
