"""Categorisation rule business rules."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Rule
from kese.repositories.categories import find_owned_category
from kese.repositories.rules import add_rule, list_owned_rules


async def create_rule(
    session: AsyncSession,
    user_id: UUID,
    pattern: str,
    category_id: UUID,
    priority: int,
) -> Rule | None:
    """Create a rule only when its category belongs to the user."""
    category = await find_owned_category(session, category_id, user_id)
    if category is None:
        return None
    rule = await add_rule(session, user_id, pattern, category_id, priority)
    await session.commit()
    return rule


async def get_rules(session: AsyncSession, user_id: UUID) -> list[Rule]:
    """Return the user's rules in priority order."""
    return await list_owned_rules(session, user_id)
