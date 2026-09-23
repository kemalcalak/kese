"""Budget request and response schemas."""

import re
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class BudgetCreate(BaseModel):
    """Fields required to create a monthly budget."""

    category_id: UUID
    month: str
    limit: Decimal = Field(gt=Decimal(0))

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        """Require a real calendar month formatted as YYYY-MM."""
        if re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value) is None:
            raise ValueError("month must use YYYY-MM format")
        return value


class BudgetResponse(BaseModel):
    """Public representation of a created budget."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    category_id: UUID
    month: str
    limit: Decimal

    @field_serializer("limit")
    def serialize_limit(self, value: Decimal) -> str:
        """Serialize money without converting it through a float."""
        return str(value)


class BudgetSummary(BudgetResponse):
    """Budget with its calculated monthly spending state."""

    spent: Decimal
    remaining: Decimal
    over: bool

    @field_serializer("spent", "remaining")
    def serialize_money(self, value: Decimal) -> str:
        """Serialize calculated money as decimal text."""
        return str(value)
