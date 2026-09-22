"""Category business rules."""

from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Category
from kese.repositories.categories import add_category, list_categories


async def create_category(
    session: AsyncSession, user_id: UUID, name: str
) -> Category | None:
    """Create a unique category for a user."""
    try:
        category = await add_category(session, user_id, name)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return None
    return category


async def get_categories(session: AsyncSession, user_id: UUID) -> list[Category]:
    """Return the user's categories."""
    return await list_categories(session, user_id)
