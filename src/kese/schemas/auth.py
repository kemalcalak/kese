"""Authentication request and response schemas."""

from uuid import UUID

from pydantic import BaseModel


class Credentials(BaseModel):
    """Credentials used to register or log in."""

    email: str
    password: str


class UserResponse(BaseModel):
    """Public user representation."""

    id: UUID
    email: str


class TokenResponse(BaseModel):
    """Access and refresh tokens."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Refresh token request body."""

    refresh_token: str


class AccessTokenResponse(BaseModel):
    """New access token response."""

    access_token: str
    token_type: str = "bearer"
