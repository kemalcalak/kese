"""Stage 3 - authentication.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.
"""

from __future__ import annotations

import asyncio
from typing import cast
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from kese.core.settings import Settings
from kese.main import create_app

PASSWORD = "correct horse battery staple"


def an_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def register(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    # cast: starlette's TestClient methods are typed as returning Any.
    return cast(
        Response,
        client.post("/auth/register", json={"email": email, "password": password}),
    )


def login(client: TestClient, email: str, password: str = PASSWORD) -> Response:
    return cast(
        Response,
        client.post("/auth/login", json={"email": email, "password": password}),
    )


def test_register_answers_the_user_without_the_password() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        response = register(client, email)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["id"]
    assert "password" not in body
    assert "hashed_password" not in body


def test_the_same_email_cannot_register_twice() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        first = register(client, email)
        second = register(client, email)

    assert first.status_code == 201
    assert second.status_code == 409


def test_login_answers_two_tokens() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        register(client, email)
        response = login(client, email)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_a_wrong_password_is_refused() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        register(client, email)
        response = login(client, email, "not the password")

    assert response.status_code == 401


def test_me_answers_the_token_holder() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        register(client, email)
        token = login(client, email).json()["access_token"]
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == email


def test_me_without_a_token_is_refused() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/auth/me")

    assert response.status_code == 401


def test_me_with_a_broken_token_is_refused() -> None:
    with TestClient(create_app()) as client:
        response = client.get(
            "/auth/me", headers={"Authorization": "Bearer not.a.token"}
        )

    assert response.status_code == 401


def test_refresh_answers_a_new_access_token() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        register(client, email)
        tokens = login(client, email).json()
        response = client.post(
            "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_the_password_is_stored_as_an_argon2_hash() -> None:
    email = an_email()

    with TestClient(create_app()) as client:
        register(client, email)

    async def stored_hash() -> str | None:
        engine = create_async_engine(Settings().database_url)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text("select hashed_password from users where email = :email"),
                    {"email": email},
                )
                return result.scalar()
        finally:
            await engine.dispose()

    hashed = asyncio.run(stored_hash())

    assert hashed is not None
    assert PASSWORD not in hashed
    assert hashed.startswith("$argon2")
