"""Category and categorisation rule HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.api.accounts import token_owner
from kese.core.database import get_session
from kese.models import User
from kese.schemas.category import CategoryCreate, CategoryResponse
from kese.schemas.rule import RuleCreate, RuleResponse
from kese.services.categories import create_category, get_categories
from kese.services.rules import create_rule, get_rules

router = APIRouter()
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(token_owner)]


@router.post("/categories", response_model=CategoryResponse, status_code=201)
async def create_category_endpoint(
    body: CategoryCreate, session: Session, user: CurrentUser
) -> CategoryResponse:
    """Create a category owned by the token holder."""
    category = await create_category(session, user.id, body.name)
    if category is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT)
    return CategoryResponse.model_validate(category)


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories_endpoint(
    session: Session, user: CurrentUser
) -> list[CategoryResponse]:
    """List categories owned by the token holder."""
    return [
        CategoryResponse.model_validate(category)
        for category in await get_categories(session, user.id)
    ]


@router.post("/rules", response_model=RuleResponse, status_code=201)
async def create_rule_endpoint(
    body: RuleCreate, session: Session, user: CurrentUser
) -> RuleResponse:
    """Create a rule pointing to the caller's category."""
    rule = await create_rule(
        session, user.id, body.pattern, body.category_id, body.priority
    )
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return RuleResponse.model_validate(rule)


@router.get("/rules", response_model=list[RuleResponse])
async def list_rules_endpoint(
    session: Session, user: CurrentUser
) -> list[RuleResponse]:
    """List rules owned by the token holder."""
    return [
        RuleResponse.model_validate(rule) for rule in await get_rules(session, user.id)
    ]
