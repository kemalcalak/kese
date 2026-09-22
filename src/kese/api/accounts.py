"""Account and transaction HTTP endpoints."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.auth import bearer_token
from kese.core.database import get_session
from kese.models import User
from kese.schemas.account import AccountCreate, AccountResponse
from kese.schemas.transaction import (
    TransactionCreate,
    TransactionPage,
    TransactionResponse,
)
from kese.services.accounts import create_account, get_accounts
from kese.services.auth import InvalidTokenError, current_user
from kese.services.transactions import (
    InvalidCursorError,
    create_transaction,
    get_transactions,
    recategorize_transactions,
)

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]


async def token_owner(request: Request, session: Session) -> User:
    """Resolve the existing access-token owner dependency for protected routes."""
    authorization = request.headers.get("Authorization")
    token = bearer_token(authorization)
    try:
        return await current_user(session, token, request.app.state.settings)
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error


CurrentUser = Annotated[User, Depends(token_owner)]


@router.post("/accounts", response_model=AccountResponse, status_code=201)
async def create_account_endpoint(
    body: AccountCreate, session: Session, user: CurrentUser
) -> AccountResponse:
    """Create an account owned by the token holder."""
    account = await create_account(session, user.id, body.name, body.currency)
    return AccountResponse(id=account.id, name=account.name, currency=account.currency)


@router.get("/accounts", response_model=list[AccountResponse])
async def list_accounts_endpoint(
    session: Session, user: CurrentUser
) -> list[AccountResponse]:
    """List only accounts owned by the token holder."""
    accounts = await get_accounts(session, user.id)
    return [
        AccountResponse(id=item.id, name=item.name, currency=item.currency)
        for item in accounts
    ]


@router.post(
    "/accounts/{account_id}/transactions",
    response_model=TransactionResponse,
    status_code=201,
)
async def create_transaction_endpoint(
    account_id: UUID,
    body: TransactionCreate,
    session: Session,
    user: CurrentUser,
) -> TransactionResponse:
    """Create a transaction on an account owned by the token holder."""
    transaction = await create_transaction(
        session,
        user.id,
        account_id,
        body.amount,
        body.occurred_at,
        body.description,
        body.category_id,
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return TransactionResponse.model_validate(transaction)


@router.get(
    "/accounts/{account_id}/transactions",
    response_model=TransactionPage,
)
async def list_transactions_endpoint(
    account_id: UUID,
    session: Session,
    user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    q: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    category_id: UUID | None = None,
) -> TransactionPage:
    """List an owned account's transactions with keyset pagination."""
    try:
        result = await get_transactions(
            session, user.id, account_id, limit, cursor, q, since, until, category_id
        )
    except InvalidCursorError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from error
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    rows, next_cursor = result
    return TransactionPage(
        items=[TransactionResponse.model_validate(item) for item in rows],
        next_cursor=next_cursor,
    )


@router.post("/transactions/recategorize")
async def recategorize_transactions_endpoint(
    session: Session, user: CurrentUser
) -> dict[str, int]:
    """Apply the caller's rules to their existing transactions."""
    return {"updated": await recategorize_transactions(session, user.id)}
