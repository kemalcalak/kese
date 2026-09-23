"""Authentication business rules."""

from uuid import UUID

import jwt
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from kese.core.security import (
    DUMMY_PASSWORD_HASH,
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from kese.core.settings import Settings
from kese.models import User
from kese.repositories.users import add_user, find_user_by_email, find_user_by_id


class DuplicateEmailError(Exception):
    """Raised when an email is already registered."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are not valid."""


class InvalidTokenError(Exception):
    """Raised when a token is missing, malformed, or the wrong kind."""


async def register_user(session: AsyncSession, email: str, password: str) -> User:
    """Create a user with an Argon2 password hash."""
    try:
        user = await add_user(session, email, hash_password(password))
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise DuplicateEmailError from error
    return user


async def login_user(
    session: AsyncSession, email: str, password: str, settings: Settings
) -> tuple[str, str]:
    """Validate credentials and issue access and refresh tokens."""
    user = await find_user_by_email(session, email)
    hashed_password = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
    if not verify_password(password, hashed_password) or user is None:
        raise InvalidCredentialsError
    return (
        create_token(user.id, settings, "access"),
        create_token(user.id, settings, "refresh"),
    )


async def current_user(session: AsyncSession, token: str, settings: Settings) -> User:
    """Resolve a bearer access token to its user."""
    try:
        user_id = decode_token(token, settings, "access")
    except (jwt.InvalidTokenError, ValueError) as error:
        raise InvalidTokenError from error
    user = await find_user_by_id(session, user_id)
    if user is None:
        raise InvalidTokenError
    return user


async def refresh_access_token(
    session: AsyncSession, token: str, settings: Settings
) -> str:
    """Validate a refresh token and issue a new access token."""
    try:
        user_id: UUID = decode_token(token, settings, "refresh")
    except (jwt.InvalidTokenError, ValueError) as error:
        raise InvalidTokenError from error
    user = await find_user_by_id(session, user_id)
    if user is None:
        raise InvalidTokenError
    return create_token(user.id, settings, "access")
