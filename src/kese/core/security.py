"""Password hashing and JWT helpers."""

from datetime import UTC, datetime, timedelta
from secrets import token_urlsafe
from typing import Any, Literal
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from kese.core.settings import Settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = password_hash.hash("invalid-user-password")
TokenKind = Literal["access", "refresh"]


def resolve_jwt_secret(settings: Settings) -> str:
    """Resolve the JWT key once, allowing local development without a secret."""
    secret = settings.jwt_secret.strip()
    if not secret:
        if settings.env == "local":
            return token_urlsafe(32)
        raise RuntimeError(
            "KESE_JWT_SECRET must be provided outside the local environment"
        )
    if settings.env != "local" and len(secret) < 32:
        raise RuntimeError("KESE_JWT_SECRET must be at least 32 characters")
    return secret


def hash_password(password: str) -> str:
    """Hash a password with the recommended Argon2 configuration."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its hash."""
    return password_hash.verify(password, hashed_password)


def create_token(
    user_id: UUID,
    settings: Settings,
    kind: TokenKind,
    jwt_secret: str | None = None,
) -> str:
    """Create a signed token with an explicit access or refresh kind."""
    lifetime = (
        settings.access_token_expire_minutes
        if kind == "access"
        else settings.refresh_token_expire_days * 24 * 60
    )
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": kind,
        "iat": now,
        "exp": now + timedelta(minutes=lifetime),
    }
    return jwt.encode(
        payload,
        jwt_secret if jwt_secret is not None else settings.jwt_secret,
        algorithm="HS256",
    )


def decode_token(
    token: str,
    settings: Settings,
    expected_kind: TokenKind,
    jwt_secret: str | None = None,
) -> UUID:
    """Decode a token and reject expired, malformed, or wrong-kind tokens."""
    payload = jwt.decode(
        token,
        jwt_secret if jwt_secret is not None else settings.jwt_secret,
        algorithms=["HS256"],
    )
    if payload.get("type") != expected_kind:
        raise jwt.InvalidTokenError("Token type is not valid for this operation")
    subject = payload.get("sub")
    if not isinstance(subject, str):
        raise jwt.InvalidTokenError("Token subject is missing")
    try:
        return UUID(subject)
    except ValueError as error:
        raise jwt.InvalidTokenError("Token subject is invalid") from error
