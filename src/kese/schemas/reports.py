"""Report response schemas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer


class CategoryReport(BaseModel):
    """Spending for one category."""

    category_id: UUID | None
    name: str
    spent: Decimal
    share: Decimal
    rank: int

    @field_serializer("spent", "share")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize money and ratios without binary floating point."""
        return str(value)


class MonthlyReport(BaseModel):
    """Income and spending for one calendar month."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    by_category: list[CategoryReport]

    @field_serializer("income", "expenses", "net")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize money without binary floating point."""
        return str(value)


class TrendPoint(BaseModel):
    """Income and spending for one trend month."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    running_net: Decimal

    @field_serializer("income", "expenses", "net", "running_net")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize money without binary floating point."""
        return str(value)
