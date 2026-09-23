"""Authentication HTTP endpoints."""

from time import monotonic
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from kese.core.database import get_session
from kese.schemas.auth import (
    AccessTokenResponse,
    Credentials,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from kese.services.auth import (
    DuplicateEmailError,
    InvalidCredentialsError,
    InvalidTokenError,
    current_user,
    login_user,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth")
Session = Annotated[AsyncSession, Depends(get_session)]


def bearer_token(authorization: str | None) -> str:
    """Extract a bearer token, returning 401 for every invalid header form."""
    if authorization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    scheme, separator, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not separator or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return token


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(credentials: Credentials, session: Session) -> UserResponse:
    """Register a user without exposing their password or hash."""
    try:
        user = await register_user(session, credentials.email, credentials.password)
    except DuplicateEmailError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT) from error
    return UserResponse(id=user.id, email=user.email)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: Credentials, request: Request, session: Session
) -> TokenResponse:
    """Authenticate a user and return access and refresh tokens."""
    limit, window = request.app.state.login_limit
    key = (
        request.client.host if request.client is not None else "unknown",
        credentials.email,
    )
    now = monotonic()
    attempts = request.app.state.login_attempts[key]
    while attempts and attempts[0] <= now - window:
        attempts.popleft()
    if len(attempts) >= limit:
        retry_after = max(1, int(attempts[0] + window - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
        )
    attempts.append(now)
    try:
        access_token, refresh_token = await login_user(
            session,
            credentials.email,
            credentials.password,
            request.app.state.settings,
            request.app.state.jwt_secret,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    session: Session,
    authorization: str | None = Header(default=None),
) -> UserResponse:
    """Return the user represented by an access bearer token."""
    token = bearer_token(authorization)
    try:
        user = await current_user(
            session, token, request.app.state.settings, request.app.state.jwt_secret
        )
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
    return UserResponse(id=user.id, email=user.email)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest, request: Request, session: Session
) -> AccessTokenResponse:
    """Exchange a refresh token for a new access token."""
    try:
        access_token = await refresh_access_token(
            session,
            body.refresh_token,
            request.app.state.settings,
            request.app.state.jwt_secret,
        )
    except InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED) from error
    return AccessTokenResponse(access_token=access_token)
