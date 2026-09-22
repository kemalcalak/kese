"""Database queries for transactions."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Transaction


async def add_transaction(
    session: AsyncSession,
    account_id: UUID,
    amount: Decimal,
    occurred_at: datetime,
    description: str,
) -> Transaction:
    """Add a transaction and flush its generated identifier."""
    transaction = Transaction(
        account_id=account_id,
        amount=amount,
        occurred_at=occurred_at,
        description=description,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def list_transactions(
    session: AsyncSession,
    account_id: UUID,
    limit: int,
    cursor: tuple[datetime, UUID] | None,
    query: str | None,
    since: datetime | None,
    until: datetime | None,
) -> list[Transaction]:
    """List transactions using keyset pagination and optional filters."""
    statement: Select[tuple[Transaction]] = select(Transaction).where(
        Transaction.account_id == account_id
    )
    if cursor is not None:
        cursor_occurred_at, cursor_id = cursor
        statement = statement.where(
            or_(
                Transaction.occurred_at < cursor_occurred_at,
                and_(
                    Transaction.occurred_at == cursor_occurred_at,
                    Transaction.id < cursor_id,
                ),
            )
        )
    if query is not None:
        statement = statement.where(Transaction.description.ilike(f"%{query}%"))
    if since is not None:
        statement = statement.where(Transaction.occurred_at >= since)
    if until is not None:
        statement = statement.where(Transaction.occurred_at <= until)
    statement = statement.order_by(
        Transaction.occurred_at.desc(), Transaction.id.desc()
    ).limit(limit + 1)
    result = await session.execute(statement)
    return list(result.scalars())
