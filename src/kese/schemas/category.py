"""Category request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreate(BaseModel):
    """Fields required to create a category."""

    name: str = Field(min_length=1, max_length=255)


class CategoryResponse(BaseModel):
    """Public category representation."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
