"""Report business rules."""

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.repositories.reports import monthly_categories, monthly_totals, monthly_trend
from kese.schemas.reports import CategoryReport, MonthlyReport, TrendPoint


def parse_month(value: str) -> date:
    """Parse a YYYY-MM value as the first day of its UTC month."""
    try:
        parsed = date.fromisoformat(f"{value}-01")
    except ValueError as error:
        raise ValueError("month must use YYYY-MM") from error
    return parsed.replace(day=1)


def next_month(value: date) -> date:
    """Return the first day of the month following value."""
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def previous_month(value: date) -> date:
    """Return the first day of the month before value."""
    if value.month == 1:
        return date(value.year - 1, 12, 1)
    return date(value.year, value.month - 1, 1)


def utc_boundary(value: date) -> datetime:
    """Convert a UTC calendar date to an aware midnight."""
    return datetime.combine(value, time.min, tzinfo=UTC)


async def get_monthly_report(
    session: AsyncSession, user_id: UUID, month: str, currency: str
) -> MonthlyReport:
    """Build a caller-isolated monthly report from SQL aggregates."""
    first = parse_month(month)
    start, end = utc_boundary(first), utc_boundary(next_month(first))
    income, expenses = await monthly_totals(session, user_id, currency, start, end)
    category_rows = await monthly_categories(session, user_id, currency, start, end)
    categories = [
        CategoryReport(
            category_id=category_id,
            name=name,
            spent=spent,
            share=spent / expenses if expenses else Decimal(0),
            rank=rank,
        )
        for category_id, name, spent, rank in category_rows
    ]
    return MonthlyReport(
        month=month,
        income=income,
        expenses=expenses,
        net=income - expenses,
        by_category=categories,
    )


async def get_trend(
    session: AsyncSession,
    user_id: UUID,
    until: str,
    months: int,
    currency: str,
) -> list[TrendPoint]:
    """Build an oldest-to-newest trend, including empty months."""
    if months < 1:
        raise ValueError("months must be positive")
    last = parse_month(until)
    first = last
    for _ in range(months - 1):
        first = previous_month(first)
    rows = await monthly_trend(
        session,
        user_id,
        currency,
        utc_boundary(first),
        utc_boundary(next_month(last)),
    )
    active = {row[0]: row for row in rows}
    running = Decimal(0)
    result: list[TrendPoint] = []
    current = first
    for _ in range(months):
        key = current.strftime("%Y-%m")
        row = active.get(key)
        if row is None:
            income = expenses = net = Decimal(0)
        else:
            _, income, expenses, net, sql_running = row
            running = sql_running
        if row is None:
            running += net
        result.append(
            TrendPoint(
                month=key,
                income=income,
                expenses=expenses,
                net=net,
                running_net=running,
            )
        )
        current = next_month(current)
    return result


def parse_day(value: str) -> date:
    """Parse an ISO UTC calendar day."""
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("date must use YYYY-MM-DD") from error


def export_range(since: str, until: str) -> tuple[datetime, datetime]:
    """Return an inclusive-day request as an exclusive UTC datetime range."""
    start_day, end_day = parse_day(since), parse_day(until)
    if end_day < start_day:
        raise ValueError("until must not precede since")
    return utc_boundary(start_day), utc_boundary(end_day + timedelta(days=1))
