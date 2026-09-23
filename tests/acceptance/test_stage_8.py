"""Stage 8 - budgets, and the alerts they raise.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.

The event stream is finite on purpose: it sends what the client has not seen,
waits `KESE_EVENTS_IDLE_SECONDS` for anything new, and closes. A browser's
EventSource reconnects on its own and sends `Last-Event-ID`, so nothing is
lost - and a test can read the stream to its end.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from kese.main import create_app

PASSWORD = "correct horse battery staple"

Headers = dict[str, str]


@pytest.fixture(autouse=True)
def a_short_idle(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KESE_EVENTS_IDLE_SECONDS", "0.2")


def an_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def a_user(client: TestClient) -> Headers:
    email = an_email()
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    tokens = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def an_account(client: TestClient, headers: Headers) -> str:
    response = client.post(
        "/accounts", json={"name": "Vadesiz", "currency": "TRY"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


def a_category(client: TestClient, headers: Headers, name: str = "Market") -> str:
    response = client.post("/categories", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


def a_budget(
    client: TestClient,
    headers: Headers,
    category_id: str,
    limit: str = "1500.00",
    month: str = "2026-05",
) -> Response:
    return cast(
        Response,
        client.post(
            "/budgets",
            json={"category_id": category_id, "month": month, "limit": limit},
            headers=headers,
        ),
    )


def spend(
    client: TestClient,
    headers: Headers,
    account_id: str,
    category_id: str,
    amount: str,
    on: str = "2026-05-10T12:00:00Z",
) -> None:
    response = client.post(
        f"/accounts/{account_id}/transactions",
        json={
            "amount": amount,
            "occurred_at": on,
            "description": "harcama",
            "category_id": category_id,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text


def budgets(client: TestClient, headers: Headers, month: str = "2026-05") -> list[Any]:
    response = client.get("/budgets", params={"month": month}, headers=headers)
    assert response.status_code == 200, response.text
    return cast(list[Any], response.json())


def events(
    client: TestClient, headers: Headers, last_event_id: str | None = None
) -> tuple[Response, list[dict[str, str]]]:
    """Read the stream to its end and parse it into events."""
    sent = dict(headers)
    if last_event_id is not None:
        sent["Last-Event-ID"] = last_event_id
    response = client.get("/budgets/events", headers=sent)
    parsed: list[dict[str, str]] = []
    for block in response.text.replace("\r\n", "\n").split("\n\n"):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            if not line or line.startswith(":"):
                continue
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        if fields.get("event"):
            parsed.append(fields)
    return cast(Response, response), parsed


def test_a_budget_belongs_to_the_caller() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        created = a_budget(client, headers, a_category(client, headers))

        mine = budgets(client, headers)
        theirs = budgets(client, a_user(client))

    assert created.status_code == 201
    assert [item["id"] for item in mine] == [created.json()["id"]]
    assert theirs == []


def test_a_budget_needs_the_callers_own_category() -> None:
    with TestClient(create_app()) as client:
        stranger = a_user(client)
        their_category = a_category(client, stranger)

        response = a_budget(client, a_user(client), their_category)

    assert response.status_code == 404


def test_one_budget_per_category_and_month() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        category = a_category(client, headers)
        a_budget(client, headers, category)

        again = a_budget(client, headers, category)
        next_month = a_budget(client, headers, category, month="2026-06")

    assert again.status_code == 409
    assert next_month.status_code == 201


def test_a_budget_limit_must_be_positive() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        category = a_category(client, headers)

        zero = a_budget(client, headers, category, limit="0")
        negative = a_budget(client, headers, category, limit="-5.00")

    assert zero.status_code == 422
    assert negative.status_code == 422


def test_spending_counts_only_that_months_expenses_in_that_category() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        market = a_category(client, headers, "Market")
        other = a_category(client, headers, "Eczane")
        a_budget(client, headers, market, limit="1500.00")

        spend(client, headers, account, market, "-400.00")
        spend(client, headers, account, market, "-300.00")
        spend(client, headers, account, market, "1000.00")
        spend(client, headers, account, market, "-999.00", on="2026-06-01T00:00:00Z")
        spend(client, headers, account, other, "-50.00")

        [budget] = budgets(client, headers)

    assert Decimal(str(budget["spent"])) == Decimal("700.00")
    assert Decimal(str(budget["remaining"])) == Decimal("800.00")
    assert budget["over"] is False


def test_crossing_the_limit_marks_the_budget_over() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = a_category(client, headers)
        a_budget(client, headers, category, limit="500.00")

        spend(client, headers, account, category, "-600.00")

        [budget] = budgets(client, headers)

    assert budget["over"] is True
    assert Decimal(str(budget["remaining"])) == Decimal("-100.00")


def test_crossing_the_limit_raises_one_alert_not_one_per_transaction() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = a_category(client, headers)
        budget_id = a_budget(client, headers, category, limit="500.00").json()["id"]

        spend(client, headers, account, category, "-300.00")
        spend(client, headers, account, category, "-300.00")
        spend(client, headers, account, category, "-100.00")

        response, received = events(client, headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event["event"] for event in received] == ["budget.exceeded"]
    payload = json.loads(received[0]["data"])
    assert payload["budget_id"] == budget_id
    assert Decimal(str(payload["spent"])) == Decimal("600.00")
    assert received[0]["id"]


def test_the_stream_resumes_after_the_last_event_id() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = a_category(client, headers)
        a_budget(client, headers, category, limit="100.00")
        spend(client, headers, account, category, "-150.00")

        _, first = events(client, headers)
        _, after = events(client, headers, last_event_id=first[0]["id"])

    assert len(first) == 1
    assert after == []


def test_a_strangers_alerts_are_not_streamed() -> None:
    with TestClient(create_app()) as client:
        owner = a_user(client)
        account = an_account(client, owner)
        category = a_category(client, owner)
        a_budget(client, owner, category, limit="100.00")
        spend(client, owner, account, category, "-150.00")

        _, received = events(client, a_user(client))

    assert received == []


def test_budgets_need_a_token() -> None:
    with TestClient(create_app()) as client:
        listing = client.get("/budgets", params={"month": "2026-05"})
        stream = client.get("/budgets/events")

    assert listing.status_code == 401
    assert stream.status_code == 401
