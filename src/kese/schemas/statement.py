"""Statement import request and response schemas."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class StatementQueuedResponse(BaseModel):
    """Representation returned when a statement import is queued."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    filename: str
    status: str


class StatementResponse(BaseModel):
    """Public representation of a statement import job."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    account_id: UUID
    filename: str
    status: str
    imported: int
    duplicates: int
    failed: int
