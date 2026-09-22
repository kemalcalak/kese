"""Database queries for statement import jobs."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Statement


async def add_statement(
    session: AsyncSession,
    account_id: UUID,
    user_id: UUID,
    filename: str,
    content: bytes,
) -> Statement:
    """Add a pending statement import job and flush its identifier."""
    statement = Statement(
        account_id=account_id,
        user_id=user_id,
        filename=filename,
        content=content,
        created_at=datetime.now(UTC),
        status="pending",
    )
    session.add(statement)
    await session.flush()
    return statement


async def find_owned_statement(
    session: AsyncSession, statement_id: UUID, user_id: UUID
) -> Statement | None:
    """Find an import job only when it belongs to the requested user."""
    result = await session.execute(
        select(Statement).where(
            Statement.id == statement_id, Statement.user_id == user_id
        )
    )
    return result.scalar_one_or_none()


async def list_owned_statements(
    session: AsyncSession, user_id: UUID
) -> list[Statement]:
    """List import jobs belonging to the requested user."""
    result = await session.execute(
        select(Statement).where(Statement.user_id == user_id).order_by(Statement.id)
    )
    return list(result.scalars())
