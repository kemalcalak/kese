"""Budget business rules."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Budget, BudgetEvent
from kese.repositories.budgets import (
    add_budget,
    add_budget_event,
    calculate_spent,
    find_budget,
    list_budget_events,
    list_budget_summaries,
)
from kese.repositories.categories import find_owned_category


class DuplicateBudgetError(Exception):
    """Raised when a category already has a budget for a month."""


async def create_budget(
    session: AsyncSession,
    user_id: UUID,
    category_id: UUID,
    month: str,
    limit: Decimal,
) -> Budget | None:
    """Create a budget for an owned category."""
    if await find_owned_category(session, category_id, user_id) is None:
        return None
    if await find_budget(session, user_id, category_id, month) is not None:
        raise DuplicateBudgetError
    try:
        budget = await add_budget(session, user_id, category_id, month, limit)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateBudgetError from error
    return budget


async def get_budget_summaries(
    session: AsyncSession, user_id: UUID, month: str
) -> list[tuple[Budget, Decimal]]:
    """Return owned budgets and their current spending."""
    return await list_budget_summaries(session, user_id, month)


async def record_budget_crossing(
    session: AsyncSession,
    user_id: UUID,
    category_id: UUID | None,
    month: str,
    amount: Decimal,
) -> BudgetEvent | None:
    """Record an event only when a transaction crosses from under to over."""
    if category_id is None or amount >= 0:
        return None
    budget = await find_budget(session, user_id, category_id, month)
    if budget is None:
        return None
    spent = await calculate_spent(session, user_id, category_id, month)
    spent_before = spent - abs(amount)
    if spent > budget.limit and spent_before <= budget.limit:
        return await add_budget_event(session, budget, spent)
    return None


async def get_budget_events(
    session: AsyncSession, user_id: UUID, last_event_id: UUID | None
) -> list[BudgetEvent]:
    """Return the caller's ordered unread budget events."""
    return await list_budget_events(session, user_id, last_event_id)
