"""Database queries for categorisation rules."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Rule


async def add_rule(
    session: AsyncSession,
    user_id: UUID,
    pattern: str,
    category_id: UUID,
    priority: int,
) -> Rule:
    """Add a rule and flush its generated identifier."""
    rule = Rule(
        user_id=user_id,
        pattern=pattern,
        category_id=category_id,
        priority=priority,
    )
    session.add(rule)
    await session.flush()
    return rule


async def list_owned_rules(session: AsyncSession, user_id: UUID) -> list[Rule]:
    """List a user's rules in matching order."""
    result = await session.execute(
        select(Rule).where(Rule.user_id == user_id).order_by(Rule.priority, Rule.id)
    )
    return list(result.scalars())
