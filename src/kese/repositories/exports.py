"""SQL queries for transaction exports."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Account, Category, Transaction


async def export_transactions(
    session: AsyncSession,
    user_id: UUID,
    start: datetime,
    end: datetime,
) -> list[tuple[datetime, str, str, str | None, Decimal]]:
    """Return only the owner's transactions in an exclusive UTC range."""
    statement = (
        select(
            Transaction.occurred_at,
            Account.name,
            Transaction.description,
            Category.name,
            Transaction.amount,
        )
        .join(Account, Transaction.account_id == Account.id)
        .outerjoin(
            Category,
            and_(Category.id == Transaction.category_id, Category.user_id == user_id),
        )
        .where(
            Account.user_id == user_id,
            Transaction.occurred_at >= start,
            Transaction.occurred_at < end,
        )
        .order_by(Transaction.occurred_at, Transaction.id)
    )
    rows = (await session.execute(statement)).all()
    return [(row[0], row[1], row[2], row[3], Decimal(row[4])) for row in rows]
