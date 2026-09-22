"""Database queries for users."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import User


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Find a user by their email address."""
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def find_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    """Find a user by their identifier."""
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def add_user(session: AsyncSession, email: str, hashed_password: str) -> User:
    """Add a user and flush it so its generated identifier is available."""
    user = User(email=email, hashed_password=hashed_password)
    session.add(user)
    await session.flush()
    return user
