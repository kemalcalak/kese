"""Database queries for budgets and budget events."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Account, Budget, BudgetEvent, Transaction


def month_bounds(month: str) -> tuple[datetime, datetime]:
    """Return inclusive/exclusive UTC bounds for a YYYY-MM month."""
    year, month_number = (int(part) for part in month.split("-"))
    if month_number == 12:
        next_month = datetime(year + 1, 1, 1, tzinfo=UTC)
    else:
        next_month = datetime(year, month_number + 1, 1, tzinfo=UTC)
    return datetime(year, month_number, 1, tzinfo=UTC), next_month


async def add_budget(
    session: AsyncSession,
    user_id: UUID,
    category_id: UUID,
    month: str,
    limit: Decimal,
) -> Budget:
    """Add a budget and flush its generated identifier."""
    budget = Budget(
        user_id=user_id,
        category_id=category_id,
        month=month,
        limit=limit,
    )
    session.add(budget)
    await session.flush()
    return budget


async def find_owned_budget(
    session: AsyncSession, budget_id: UUID, user_id: UUID
) -> Budget | None:
    """Find a budget owned by a user."""
    result = await session.execute(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def find_budget(
    session: AsyncSession, user_id: UUID, category_id: UUID, month: str
) -> Budget | None:
    """Find the budget for one owner, category, and month."""
    result = await session.execute(
        select(Budget).where(
            Budget.user_id == user_id,
            Budget.category_id == category_id,
            Budget.month == month,
        )
    )
    return result.scalar_one_or_none()


async def list_budget_summaries(
    session: AsyncSession, user_id: UUID, month: str
) -> list[tuple[Budget, Decimal]]:
    """List owned budgets and expense totals for a month."""
    start, end = month_bounds(month)
    spending = and_(
        Transaction.category_id == Budget.category_id,
        Transaction.amount < 0,
        Transaction.occurred_at >= start,
        Transaction.occurred_at < end,
    )
    statement: Select[tuple[Budget, Decimal]] = (
        select(Budget, func.coalesce(func.sum(-Transaction.amount), 0))
        .outerjoin(
            Transaction,
            and_(
                spending,
                Transaction.account_id.in_(
                    select(Account.id).where(Account.user_id == user_id)
                ),
            ),
        )
        .where(Budget.user_id == user_id, Budget.month == month)
        .group_by(Budget.id)
        .order_by(Budget.id)
    )
    result = await session.execute(statement)
    return [(budget, Decimal(spent)) for budget, spent in result.all()]


async def calculate_spent(
    session: AsyncSession, user_id: UUID, category_id: UUID, month: str
) -> Decimal:
    """Calculate expense spending for an owned category and month."""
    start, end = month_bounds(month)
    result = await session.execute(
        select(func.coalesce(func.sum(-Transaction.amount), 0))
        .join(Account, Account.id == Transaction.account_id)
        .where(
            Account.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.amount < 0,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
    )
    return Decimal(result.scalar_one())


async def add_budget_event(
    session: AsyncSession,
    budget: Budget,
    spent: Decimal,
) -> BudgetEvent:
    """Record one budget crossing event."""
    event = BudgetEvent(
        budget_id=budget.id,
        user_id=budget.user_id,
        category_id=budget.category_id,
        month=budget.month,
        limit=budget.limit,
        spent=spent,
    )
    session.add(event)
    await session.flush()
    return event


async def list_budget_events(
    session: AsyncSession, user_id: UUID, last_event_id: UUID | None
) -> list[BudgetEvent]:
    """List a user's events after an optional event cursor."""
    statement: Select[tuple[BudgetEvent]] = select(BudgetEvent).where(
        BudgetEvent.user_id == user_id
    )
    if last_event_id is not None:
        reference = await session.get(BudgetEvent, last_event_id)
        if reference is not None and reference.user_id == user_id:
            statement = statement.where(
                or_(
                    BudgetEvent.created_at > reference.created_at,
                    and_(
                        BudgetEvent.created_at == reference.created_at,
                        BudgetEvent.id > reference.id,
                    ),
                )
            )
    statement = statement.order_by(BudgetEvent.created_at, BudgetEvent.id)
    result = await session.execute(statement)
    return list(result.scalars())
