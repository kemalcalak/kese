"""Stage 5 - categories and the rules that apply them.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.
"""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response

from kese.main import create_app

PASSWORD = "correct horse battery staple"

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


def an_account(client: TestClient, headers: Headers) -> dict[str, Any]:
    response = client.post(
        "/accounts", json={"name": "Vadesiz", "currency": "TRY"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def a_category(client: TestClient, headers: Headers, name: str) -> dict[str, Any]:
    response = client.post("/categories", json={"name": name}, headers=headers)
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def a_rule(
    client: TestClient,
    headers: Headers,
    pattern: str,
    category_id: str,
    priority: int = 10,
) -> Response:
    return cast(
        Response,
        client.post(
            "/rules",
            json={"pattern": pattern, "category_id": category_id, "priority": priority},
            headers=headers,
        ),
    )


def a_transaction(
    client: TestClient,
    headers: Headers,
    account_id: str,
    description: str,
    **extra: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "amount": "-100.00",
        "occurred_at": "2026-04-01T10:00:00Z",
        "description": description,
    }
    body.update(extra)
    response = client.post(
        f"/accounts/{account_id}/transactions", json=body, headers=headers
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def transactions(
    client: TestClient, headers: Headers, account_id: str, **query: Any
) -> dict[str, Any]:
    response = client.get(
        f"/accounts/{account_id}/transactions", params=query, headers=headers
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def test_a_category_belongs_to_the_caller() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        category = a_category(client, headers, "Market")

        listing = client.get("/categories", headers=headers)
        stranger = client.get("/categories", headers=a_user(client))

    assert category["name"] == "Market"
    assert [item["id"] for item in listing.json()] == [category["id"]]
    assert stranger.json() == []


def test_one_user_cannot_repeat_a_category_name() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        a_category(client, headers, "Market")

        again = client.post("/categories", json={"name": "Market"}, headers=headers)
        elsewhere = client.post(
            "/categories", json={"name": "Market"}, headers=a_user(client)
        )

    assert again.status_code == 409
    assert elsewhere.status_code == 201


def test_a_rule_categorises_a_new_transaction() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = a_category(client, headers, "Market")
        a_rule(client, headers, "migros", category["id"])

        created = a_transaction(client, headers, account["id"], "MIGROS ATASEHIR")

    assert created["category_id"] == category["id"]


def test_a_transaction_nothing_matches_has_no_category() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        a_rule(client, headers, "migros", a_category(client, headers, "Market")["id"])

        created = a_transaction(client, headers, account["id"], "eczane")

    assert created["category_id"] is None


def test_the_smaller_priority_wins() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        general = a_category(client, headers, "Alışveriş")
        specific = a_category(client, headers, "Market")
        a_rule(client, headers, "migros", general["id"], priority=20)
        a_rule(client, headers, "migros atasehir", specific["id"], priority=1)

        created = a_transaction(client, headers, account["id"], "MIGROS ATASEHIR")

    assert created["category_id"] == specific["id"]


def test_an_explicit_category_beats_the_rules() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        automatic = a_category(client, headers, "Market")
        chosen = a_category(client, headers, "Hediye")
        a_rule(client, headers, "migros", automatic["id"])

        created = a_transaction(
            client, headers, account["id"], "MIGROS ATASEHIR", category_id=chosen["id"]
        )

    assert created["category_id"] == chosen["id"]


def test_another_users_rules_do_not_apply() -> None:
    with TestClient(create_app()) as client:
        stranger = a_user(client)
        a_rule(client, stranger, "migros", a_category(client, stranger, "Market")["id"])

        headers = a_user(client)
        account = an_account(client, headers)
        created = a_transaction(client, headers, account["id"], "MIGROS ATASEHIR")

    assert created["category_id"] is None


def test_a_rule_needs_one_of_the_callers_own_categories() -> None:
    with TestClient(create_app()) as client:
        stranger = a_user(client)
        theirs = a_category(client, stranger, "Market")

        headers = a_user(client)
        response = a_rule(client, headers, "migros", theirs["id"])

    assert response.status_code == 404


def test_recategorizing_applies_a_later_rule_to_older_transactions() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        before = a_transaction(client, headers, account["id"], "MIGROS ATASEHIR")

        category = a_category(client, headers, "Market")
        a_rule(client, headers, "migros", category["id"])
        applied = client.post("/transactions/recategorize", headers=headers)

        listed = transactions(client, headers, account["id"])

    assert before["category_id"] is None
    assert applied.status_code == 200
    assert applied.json()["updated"] == 1
    assert [item["category_id"] for item in listed["items"]] == [category["id"]]


def test_the_listing_filters_by_category() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = a_category(client, headers, "Market")
        a_rule(client, headers, "migros", category["id"])
        a_transaction(client, headers, account["id"], "MIGROS ATASEHIR")
        a_transaction(client, headers, account["id"], "eczane")

        listed = transactions(
            client, headers, account["id"], category_id=category["id"]
        )

    assert [item["description"] for item in listed["items"]] == ["MIGROS ATASEHIR"]
