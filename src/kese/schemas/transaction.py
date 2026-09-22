"""Transaction request and response schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator


class TransactionCreate(BaseModel):
    """Fields required to create a transaction."""

    amount: Decimal
    occurred_at: datetime
    description: str

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        """Require an explicit timezone on transaction timestamps."""
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value


class TransactionResponse(BaseModel):
    """Public transaction representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    amount: Decimal
    occurred_at: datetime
    description: str

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Serialize money without converting it through a binary float."""
        return str(value)


class TransactionPage(BaseModel):
    """Cursor-paginated transaction response."""

    items: list[TransactionResponse]
    next_cursor: str | None
