"""Transaction business rules."""

import base64
import binascii
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from kese.models import Transaction
from kese.repositories.accounts import find_owned_account
from kese.repositories.categories import find_owned_category
from kese.repositories.rules import list_owned_rules
from kese.repositories.transactions import (
    add_transaction,
    list_transactions,
    list_user_transactions,
)


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
    category_id: UUID | None,
) -> Transaction | None:
    """Create a transaction only for an account owned by the user."""
    account = await find_owned_account(session, account_id, user_id)
    if account is None:
        return None
    if category_id is not None:
        if await find_owned_category(session, category_id, user_id) is None:
            return None
    else:
        rules = await list_owned_rules(session, user_id)
        lowered_description = description.casefold()
        matching_rule = next(
            (rule for rule in rules if rule.pattern.casefold() in lowered_description),
            None,
        )
        category_id = matching_rule.category_id if matching_rule is not None else None
    transaction = await add_transaction(
        session,
        account.id,
        amount,
        utc_datetime(occurred_at),
        description,
        category_id,
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
    category_id: UUID | None,
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
        category_id,
    )
    next_cursor = encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], next_cursor


async def recategorize_transactions(session: AsyncSession, user_id: UUID) -> int:
    """Apply the user's current rules to all their transactions."""
    rules = await list_owned_rules(session, user_id)
    transactions = await list_user_transactions(session, user_id)
    updated = 0
    for transaction in transactions:
        lowered_description = transaction.description.casefold()
        matching_rule = next(
            (rule for rule in rules if rule.pattern.casefold() in lowered_description),
            None,
        )
        category_id = matching_rule.category_id if matching_rule is not None else None
        if transaction.category_id != category_id:
            transaction.category_id = category_id
            updated += 1
    await session.commit()
    return updated
