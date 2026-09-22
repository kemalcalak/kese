"""Statement import business rules."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Statement
from kese.repositories.accounts import find_owned_account
from kese.repositories.statements import (
    add_statement,
    find_owned_statement,
    list_owned_statements,
)


async def queue_statement(
    session: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    filename: str,
    content: bytes,
) -> Statement | None:
    """Queue a pending statement only for an account owned by the user."""
    account = await find_owned_account(session, account_id, user_id)
    if account is None:
        return None
    statement = await add_statement(session, account.id, user_id, filename, content)
    await session.commit()
    return statement


async def get_statement(
    session: AsyncSession, user_id: UUID, statement_id: UUID
) -> Statement | None:
    """Return a statement import job owned by the user."""
    return await find_owned_statement(session, statement_id, user_id)


async def get_statements(session: AsyncSession, user_id: UUID) -> list[Statement]:
    """Return all statement import jobs owned by the user."""
    return await list_owned_statements(session, user_id)
