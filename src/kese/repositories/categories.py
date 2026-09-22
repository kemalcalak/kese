"""Database queries for categories."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Category


async def add_category(session: AsyncSession, user_id: UUID, name: str) -> Category:
    """Add a category and flush its generated identifier."""
    category = Category(user_id=user_id, name=name)
    session.add(category)
    await session.flush()
    return category


async def list_categories(session: AsyncSession, user_id: UUID) -> list[Category]:
    """List categories owned by a user."""
    result = await session.execute(
        select(Category).where(Category.user_id == user_id).order_by(Category.name)
    )
    return list(result.scalars())


async def find_owned_category(
    session: AsyncSession, category_id: UUID, user_id: UUID
) -> Category | None:
    """Find a category owned by a user."""
    result = await session.execute(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    return result.scalar_one_or_none()
