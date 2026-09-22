"""Account request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class AccountCreate(BaseModel):
    """Fields required to create an account."""

    name: str = Field(min_length=1)
    currency: str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        """Require an ISO-style three-letter uppercase currency code."""
        if len(value) != 3 or not value.isascii() or not value.isupper():
            raise ValueError("currency must be three ASCII uppercase letters")
        return value


class AccountResponse(BaseModel):
    """Public account representation."""

    id: UUID
    name: str
    currency: str
