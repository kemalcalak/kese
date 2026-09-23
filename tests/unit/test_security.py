"""Unit tests for JWT secret resolution."""

from __future__ import annotations

import pytest

from kese.core.security import resolve_jwt_secret
from kese.core.settings import Settings


def test_settings_read_a_missing_jwt_secret_without_validation() -> None:
    settings = Settings(env="test", jwt_secret="   ")

    assert settings.jwt_secret == "   "


def test_local_resolution_generates_a_secret_without_mutating_settings() -> None:
    settings = Settings(env="local", jwt_secret="")

    resolved = resolve_jwt_secret(settings)

    assert len(resolved) >= 32
    assert settings.jwt_secret == ""


@pytest.mark.parametrize("secret", ["", "   ", "too-short"])
def test_non_local_resolution_requires_a_jwt_secret(secret: str) -> None:
    with pytest.raises(RuntimeError, match="KESE_JWT_SECRET"):
        resolve_jwt_secret(Settings(env="production", jwt_secret=secret))


def test_non_local_resolution_returns_a_valid_secret() -> None:
    secret = "x" * 32

    assert resolve_jwt_secret(Settings(env="production", jwt_secret=secret)) == secret
