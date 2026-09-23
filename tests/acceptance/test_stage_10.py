"""Stage 10 - hardening.

Written by hand before the stage and never edited except to fix the test
itself: it states what the stage has to do. It needs the compose database up
and the migrations applied.

Every error has one shape, every request one id and one log line, logins are
rate limited, production will not start on a throwaway secret, and the image
runs as someone other than root and never carries the `.env`.

Two tests were added after the stage, from running the image: an empty secret
passed the production check (compose writes one when the variable is unset),
and the access log existed only for pytest's `caplog` - in the container not
one line of it reached the output.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from kese.main import create_app

PASSWORD = "correct horse battery staple"
ROOT = Path(__file__).resolve().parents[2]

Headers = dict[str, str]


def an_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def a_user(client: TestClient) -> Headers:
    email = an_email()
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    tokens = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def envelope(body: Any) -> dict[str, Any]:
    assert set(body) == {"error"}, body
    error = cast(dict[str, Any], body["error"])
    assert {"code", "message", "request_id"} <= set(error), error
    return error


def test_every_response_carries_a_request_id() -> None:
    with TestClient(create_app()) as client:
        first = client.get("/health")
        second = client.get("/health")

    assert first.headers["X-Request-ID"]
    assert second.headers["X-Request-ID"]
    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_a_request_id_the_client_sent_is_kept() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": "trace-me-123"})

    assert response.headers["X-Request-ID"] == "trace-me-123"


def test_every_error_has_the_same_envelope() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        client.post("/categories", json={"name": "Market"}, headers=headers)

        unauthorized = client.get("/accounts")
        missing = client.get(f"/statements/{uuid4()}", headers=headers)
        conflict = client.post("/categories", json={"name": "Market"}, headers=headers)
        invalid = client.post(
            "/accounts", json={"name": "Vadesiz", "currency": "lira"}, headers=headers
        )

    codes = {
        401: envelope(unauthorized.json())["code"],
        404: envelope(missing.json())["code"],
        409: envelope(conflict.json())["code"],
        422: envelope(invalid.json())["code"],
    }
    assert codes == {
        401: "unauthorized",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }
    assert envelope(missing.json())["request_id"] == missing.headers["X-Request-ID"]


def test_an_unexpected_error_is_an_envelope_that_says_nothing_inside() -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("the database password is hunter2")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    error = envelope(response.json())
    assert error["code"] == "internal_error"
    assert "hunter2" not in response.text
    assert error["request_id"] == response.headers["X-Request-ID"]


def test_logins_to_one_account_are_rate_limited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KESE_LOGIN_RATE_LIMIT", "3/minute")
    email = an_email()

    with TestClient(create_app()) as client:
        client.post("/auth/register", json={"email": email, "password": PASSWORD})
        attempts = [
            client.post("/auth/login", json={"email": email, "password": "wrong"})
            for _ in range(4)
        ]
        someone_else = client.post(
            "/auth/login", json={"email": an_email(), "password": "wrong"}
        )

    assert [response.status_code for response in attempts] == [401, 401, 401, 429]
    assert envelope(attempts[-1].json())["code"] == "rate_limited"
    assert int(attempts[-1].headers["Retry-After"]) > 0
    assert someone_else.status_code == 401


def test_each_request_is_one_json_log_line(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="kese.access")

    with TestClient(create_app()) as client:
        response = client.get("/health")

    entries = [
        json.loads(record.getMessage())
        for record in caplog.records
        if record.name == "kese.access"
    ]
    [entry] = [entry for entry in entries if entry["path"] == "/health"]
    assert entry["method"] == "GET"
    assert entry["status"] == 200
    assert entry["request_id"] == response.headers["X-Request-ID"]
    assert isinstance(entry["duration_ms"], int | float)


def test_the_logs_never_carry_a_password_or_a_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)

    with TestClient(create_app()) as client:
        headers = a_user(client)
        client.get("/auth/me", headers=headers)

    logged = "\n".join(record.getMessage() for record in caplog.records)
    token = headers["Authorization"].split()[1]
    assert PASSWORD not in logged
    assert token not in logged


def test_production_refuses_to_start_without_a_jwt_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KESE_ENV", "production")
    monkeypatch.delenv("KESE_JWT_SECRET", raising=False)

    with pytest.raises((RuntimeError, ValueError), match="KESE_JWT_SECRET"):
        create_app()


@pytest.mark.parametrize("secret", ["", "   ", "too-short"])
def test_production_refuses_an_empty_or_short_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    monkeypatch.setenv("KESE_ENV", "production")
    monkeypatch.setenv("KESE_JWT_SECRET", secret)

    with pytest.raises((RuntimeError, ValueError), match="KESE_JWT_SECRET"):
        create_app()


def test_production_starts_with_a_real_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KESE_ENV", "production")
    monkeypatch.setenv("KESE_JWT_SECRET", "x" * 32)

    assert create_app().title == "kese"


def test_the_access_log_reaches_the_process_output() -> None:
    """In a plain process - no pytest, no caplog - a request is one JSON line."""
    script = (
        "from fastapi.testclient import TestClient\n"
        "from kese.main import create_app\n"
        "with TestClient(create_app()) as client:\n"
        "    client.get('/health')\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )

    entries = []
    for line in (done.stdout + done.stderr).splitlines():
        if line.startswith("{"):
            entries.append(json.loads(line))
    assert any(entry.get("path") == "/health" for entry in entries), done.stderr


def test_local_development_still_starts_without_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("KESE_ENV", "local")
    monkeypatch.delenv("KESE_JWT_SECRET", raising=False)

    assert create_app().title == "kese"


def test_local_development_treats_an_empty_secret_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Compose passes `KESE_JWT_SECRET=""` when the variable is not set."""
    monkeypatch.setenv("KESE_ENV", "local")
    monkeypatch.setenv("KESE_JWT_SECRET", "")

    assert create_app().title == "kese"


def test_the_image_runs_as_someone_other_than_root_and_starts_the_app() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    users = [
        line.split()[1]
        for line in dockerfile.splitlines()
        if line.strip().upper().startswith("USER ")
    ]
    assert users, "the Dockerfile never switches user"
    assert users[-1] not in {"root", "0"}
    assert "kese.main:app" in dockerfile


def test_the_image_never_carries_the_env_file() -> None:
    ignored = {
        line.strip().strip("/")
        for line in (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    }

    assert ".env" in ignored
    assert ".venv" in ignored
