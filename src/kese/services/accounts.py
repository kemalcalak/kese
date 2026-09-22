"""Account business rules."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Account
from kese.repositories.accounts import add_account, list_accounts


async def create_account(
    session: AsyncSession, user_id: UUID, name: str, currency: str
) -> Account:
    """Create and commit an account owned by the user."""
    account = await add_account(session, user_id, name, currency)
    await session.commit()
    return account


async def get_accounts(session: AsyncSession, user_id: UUID) -> list[Account]:
    """Return all accounts owned by the user."""
    return await list_accounts(session, user_id)
