"""Transaction business rules."""

import base64
import binascii
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Transaction
from kese.repositories.accounts import find_owned_account
from kese.repositories.transactions import add_transaction, list_transactions


class InvalidCursorError(ValueError):
    """Raised when a cursor cannot be decoded."""


def encode_cursor(transaction: Transaction) -> str:
    """Encode the last row's sort keys into an opaque URL-safe cursor."""
    value = f"{transaction.occurred_at.isoformat()}|{transaction.id}"
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_cursor(value: str) -> tuple[datetime, UUID]:
    """Decode a cursor into the occurred-at and id sort keys."""
    try:
        padded = value + "=" * (-len(value) % 4)
        raw_occurred_at, raw_id = (
            base64.urlsafe_b64decode(padded).decode().split("|", 1)
        )
        occurred_at = datetime.fromisoformat(raw_occurred_at)
        if occurred_at.tzinfo is None:
            raise ValueError
        return occurred_at, UUID(raw_id)
    except (ValueError, UnicodeError, binascii.Error) as error:
        raise InvalidCursorError from error


def utc_datetime(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC for storage and comparisons."""
    if value.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware")
    return value.astimezone(UTC)


async def create_transaction(
    session: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    amount: Decimal,
    occurred_at: datetime,
    description: str,
) -> Transaction | None:
    """Create a transaction only for an account owned by the user."""
    account = await find_owned_account(session, account_id, user_id)
    if account is None:
        return None
    transaction = await add_transaction(
        session,
        account.id,
        amount,
        utc_datetime(occurred_at),
        description,
    )
    await session.commit()
    return transaction


async def get_transactions(
    session: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    limit: int,
    cursor: str | None,
    query: str | None,
    since: datetime | None,
    until: datetime | None,
) -> tuple[list[Transaction], str | None] | None:
    """Return an owned account's transactions and the next cursor."""
    account = await find_owned_account(session, account_id, user_id)
    if account is None:
        return None
    decoded_cursor = decode_cursor(cursor) if cursor is not None else None
    rows = await list_transactions(
        session,
        account.id,
        limit,
        decoded_cursor,
        query,
        utc_datetime(since) if since is not None else None,
        utc_datetime(until) if until is not None else None,
    )
    next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], next_cursor
