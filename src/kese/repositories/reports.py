"""SQL aggregate queries for reports."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, case, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Account, Category, Transaction


async def monthly_totals(
    session: AsyncSession,
    user_id: UUID,
    currency: str,
    start: datetime,
    end: datetime,
) -> tuple[Decimal, Decimal]:
    """Return income and expenses for the owner's accounts in one UTC month."""
    income = func.coalesce(
        func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0)), 0
    )
    expenses = func.coalesce(
        func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0)), 0
    )
    statement = (
        select(income, expenses)
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user_id,
            Account.currency == currency,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
    )
    row = (await session.execute(statement)).one()
    return Decimal(row[0]), Decimal(row[1])


async def monthly_categories(
    session: AsyncSession,
    user_id: UUID,
    currency: str,
    start: datetime,
    end: datetime,
) -> list[tuple[UUID | None, str, Decimal, int]]:
    """Return ranked expense categories using SQL grouping and RANK."""
    spent = func.sum(-Transaction.amount).label("spent")
    category_name = case(
        (Transaction.category_id.is_(None), literal("Uncategorised")),
        else_=Category.name,
    ).label("name")
    grouped = (
        select(Transaction.category_id.label("category_id"), category_name, spent)
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(
            Category,
            and_(
                Transaction.category_id == Category.id,
                Category.user_id == user_id,
            ),
        )
        .where(
            Account.user_id == user_id,
            Account.currency == currency,
            Transaction.amount < 0,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
        .group_by(Transaction.category_id, Category.name)
        .subquery()
    )
    rank = func.rank().over(order_by=grouped.c.spent.desc())
    statement: Select[tuple[UUID | None, str, Decimal, int]] = select(
        grouped.c.category_id,
        grouped.c.name,
        grouped.c.spent,
        rank,
    ).order_by(grouped.c.spent.desc(), grouped.c.name.asc())
    rows = (await session.execute(statement)).all()
    return [(row[0], row[1], Decimal(row[2]), int(row[3])) for row in rows]


async def monthly_trend(
    session: AsyncSession,
    user_id: UUID,
    currency: str,
    start: datetime,
    end: datetime,
) -> list[tuple[str, Decimal, Decimal, Decimal, Decimal]]:
    """Return active months and SQL-computed cumulative net totals."""
    month = func.date_trunc("month", func.timezone("UTC", Transaction.occurred_at))
    income = func.sum(case((Transaction.amount > 0, Transaction.amount), else_=0))
    expenses = func.sum(case((Transaction.amount < 0, -Transaction.amount), else_=0))
    grouped = (
        select(
            month.label("month"),
            func.coalesce(income, 0).label("income"),
            func.coalesce(expenses, 0).label("expenses"),
        )
        .join(Account, Transaction.account_id == Account.id)
        .where(
            Account.user_id == user_id,
            Account.currency == currency,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
        .group_by(month)
        .subquery()
    )
    net = (grouped.c.income - grouped.c.expenses).label("net")
    running_net = func.sum(net).over(order_by=grouped.c.month).label("running_net")
    statement = select(
        grouped.c.month, grouped.c.income, grouped.c.expenses, net, running_net
    )
    rows = (await session.execute(statement.order_by(grouped.c.month))).all()
    return [
        (
            row[0].strftime("%Y-%m"),
            Decimal(row[1]),
            Decimal(row[2]),
            Decimal(row[3]),
            Decimal(row[4]),
        )
        for row in rows
    ]
