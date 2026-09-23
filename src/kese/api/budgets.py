"""Budget and budget-event HTTP endpoints."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.schemas.budget import BudgetCreate, BudgetResponse, BudgetSummary
from kese.services.budgets import (
    DuplicateBudgetError,
    create_budget,
    get_budget_events,
    get_budget_summaries,
)

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]


@router.post(
    "/budgets", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED
)
async def create_budget_endpoint(
    body: BudgetCreate, session: Session, user: CurrentUser
) -> BudgetResponse:
    """Create a budget for the caller's category."""
    try:
        budget = await create_budget(
            session, user.id, body.category_id, body.month, body.limit
        )
    except DuplicateBudgetError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT) from error
    if budget is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return BudgetResponse.model_validate(budget)


@router.get("/budgets", response_model=list[BudgetSummary])
async def list_budgets_endpoint(
    month: Annotated[str, Query(pattern=r"\d{4}-(0[1-9]|1[0-2])")],
    session: Session,
    user: CurrentUser,
) -> list[BudgetSummary]:
    """List the caller's budgets with monthly spending totals."""
    try:
        summaries = await get_budget_summaries(session, user.id, month)
    except (ValueError, IndexError) as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from error
    return [
        BudgetSummary(
            id=budget.id,
            category_id=budget.category_id,
            month=budget.month,
            limit=budget.limit,
            spent=spent,
            remaining=budget.limit - spent,
            over=spent > budget.limit,
        )
        for budget, spent in summaries
    ]


async def event_stream(
    request: Request,
    session: AsyncSession,
    user_id: UUID,
    last_event_id: UUID | None,
    idle_seconds: float,
) -> AsyncIterator[str]:
    """Yield unread events, then wait once for new events before closing."""
    events_sent = False
    while True:
        events = await get_budget_events(session, user_id, last_event_id)
        if events:
            for event in events:
                payload = json.dumps(
                    {
                        "budget_id": str(event.budget_id),
                        "category_id": str(event.category_id),
                        "month": event.month,
                        "limit": str(event.limit),
                        "spent": str(event.spent),
                    },
                    separators=(",", ":"),
                )
                yield (f"id: {event.id}\nevent: budget.exceeded\ndata: {payload}\n\n")
                last_event_id = event.id
                events_sent = True
            continue
        if events_sent:
            await asyncio.sleep(idle_seconds)
            if await request.is_disconnected():
                return
            events_sent = False
            continue
        await asyncio.sleep(idle_seconds)
        return


@router.get("/budgets/events")
async def budget_events_endpoint(
    request: Request,
    session: Session,
    user: CurrentUser,
    last_event_id: Annotated[UUID | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream the caller's unread budget exceeded events."""
    return StreamingResponse(
        event_stream(
            request,
            session,
            user.id,
            last_event_id,
            request.app.state.settings.events_idle_seconds,
        ),
        media_type="text/event-stream",
    )
