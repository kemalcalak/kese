"""Statement import HTTP endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.schemas.statement import StatementQueuedResponse, StatementResponse
from kese.services.statements import get_statement, get_statements, queue_statement

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]


@router.post(
    "/accounts/{account_id}/statements",
    response_model=StatementQueuedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_statement(
    account_id: UUID,
    file: UploadFile,
    session: Session,
    user: CurrentUser,
) -> StatementResponse:
    """Queue a CSV or XLSX statement without parsing its contents."""
    filename = file.filename or ""
    if not filename.lower().endswith((".csv", ".xlsx")):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
    content = await file.read()
    statement = await queue_statement(session, user.id, account_id, filename, content)
    if statement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return StatementResponse.model_validate(statement)


@router.get("/statements/{statement_id}", response_model=StatementResponse)
async def get_statement_endpoint(
    statement_id: UUID,
    session: Session,
    user: CurrentUser,
) -> StatementResponse:
    """Return an import job owned by the token holder."""
    statement = await get_statement(session, user.id, statement_id)
    if statement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return StatementResponse.model_validate(statement)


@router.get("/statements", response_model=list[StatementResponse])
async def list_statements_endpoint(
    session: Session,
    user: CurrentUser,
) -> list[StatementResponse]:
    """List import jobs owned by the token holder."""
    statements = await get_statements(session, user.id)
    return [StatementResponse.model_validate(item) for item in statements]
