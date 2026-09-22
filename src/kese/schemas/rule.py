"""Categorisation rule request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleCreate(BaseModel):
    """Fields required to create a categorisation rule."""

    pattern: str = Field(min_length=1, max_length=255)
    category_id: UUID
    priority: int = 10


class RuleResponse(BaseModel):
    """Public rule representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pattern: str
    category_id: UUID
    priority: int
