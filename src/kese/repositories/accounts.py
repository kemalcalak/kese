"""Database queries for accounts."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Account


async def add_account(
    session: AsyncSession, user_id: UUID, name: str, currency: str
) -> Account:
    """Add an account for a user and flush its generated identifier."""
    account = Account(user_id=user_id, name=name, currency=currency)
    session.add(account)
    await session.flush()
    return account


async def list_accounts(session: AsyncSession, user_id: UUID) -> list[Account]:
    """List only accounts owned by a user."""
    result = await session.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.id)
    )
    return list(result.scalars())


async def find_owned_account(
    session: AsyncSession, account_id: UUID, user_id: UUID
) -> Account | None:
    """Find an account only when it belongs to the requested user."""
    result = await session.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    return result.scalar_one_or_none()
