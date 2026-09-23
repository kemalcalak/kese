"""Exchange-rate API schemas."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_serializer


class ExchangeRateResponse(BaseModel):
    """A cached or freshly fetched exchange rate."""

    code: str
    on: date
    rate_date: date
    rate: Decimal

    @field_serializer("rate")
    def serialize_rate(self, value: Decimal) -> str:
        """Serialize rates as exact decimal strings."""
        return str(value)


class ConversionResponse(BaseModel):
    """A currency conversion result."""

    amount: Decimal
    rate: Decimal
    converted: Decimal

    @field_serializer("amount", "rate", "converted")
    def serialize_decimal(self, value: Decimal) -> str:
        """Serialize monetary values without a binary float conversion."""
        return str(value)
