"""Stage 4 - accounts and transactions.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from kese.core.settings import Settings
from kese.main import create_app

PASSWORD = "correct horse battery staple"

Headers = dict[str, str]


def an_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def a_user(client: TestClient) -> Headers:
    """Register a fresh user and return its authorization header."""
    email = an_email()
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    tokens = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def an_account(
    client: TestClient, headers: Headers, name: str = "Vadesiz", currency: str = "TRY"
) -> dict[str, Any]:
    response = client.post(
        "/accounts", json={"name": name, "currency": currency}, headers=headers
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def a_transaction(
    client: TestClient,
    headers: Headers,
    account_id: str,
    amount: str,
    occurred_at: str = "2026-02-01T10:00:00Z",
    description: str = "market",
) -> Response:
    return cast(
        Response,
        client.post(
            f"/accounts/{account_id}/transactions",
            json={
                "amount": amount,
                "occurred_at": occurred_at,
                "description": description,
            },
            headers=headers,
        ),
    )


def transactions(
    client: TestClient, headers: Headers, account_id: str, **query: Any
) -> dict[str, Any]:
    response = client.get(
        f"/accounts/{account_id}/transactions", params=query, headers=headers
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def test_an_account_belongs_to_the_caller() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers, name="Maaş", currency="TRY")

        listing = client.get("/accounts", headers=headers)

    assert account["name"] == "Maaş"
    assert account["currency"] == "TRY"
    assert listing.status_code == 200
    assert [item["id"] for item in listing.json()] == [account["id"]]


def test_accounts_need_a_token() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/accounts")

    assert response.status_code == 401


def test_another_user_can_neither_see_nor_use_the_account() -> None:
    with TestClient(create_app()) as client:
        owner = a_user(client)
        account = an_account(client, owner)
        stranger = a_user(client)

        listing = client.get("/accounts", headers=stranger)
        reading = client.get(
            f"/accounts/{account['id']}/transactions", headers=stranger
        )
        writing = a_transaction(client, stranger, account["id"], "-10.00")

    assert listing.json() == []
    assert reading.status_code == 404
    assert writing.status_code == 404


def test_an_unknown_currency_is_refused() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        response = client.post(
            "/accounts", json={"name": "Vadesiz", "currency": "lira"}, headers=headers
        )

    assert response.status_code == 422


def test_an_amount_round_trips_to_the_kurus() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)

        created = a_transaction(client, headers, account["id"], "-1234.56")
        big = a_transaction(client, headers, account["id"], "9999999.99")
        listed = transactions(client, headers, account["id"])

    assert created.status_code == 201
    assert Decimal(str(created.json()["amount"])) == Decimal("-1234.56")
    assert Decimal(str(big.json()["amount"])) == Decimal("9999999.99")
    assert {Decimal(str(item["amount"])) for item in listed["items"]} == {
        Decimal("-1234.56"),
        Decimal("9999999.99"),
    }


def test_the_amount_column_is_numeric() -> None:
    async def column_type() -> str | None:
        engine = create_async_engine(Settings().database_url)
        try:
            async with engine.connect() as connection:
                result = await connection.execute(
                    text(
                        "select data_type from information_schema.columns "
                        "where table_name = 'transactions' and column_name = 'amount'"
                    )
                )
                return result.scalar()
        finally:
            await engine.dispose()

    assert asyncio.run(column_type()) == "numeric"


def test_transactions_come_back_newest_first() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        for day, description in (("01", "kira"), ("02", "market"), ("03", "fatura")):
            a_transaction(
                client,
                headers,
                account["id"],
                "-100.00",
                occurred_at=f"2026-03-{day}T09:00:00Z",
                description=description,
            )

        listed = transactions(client, headers, account["id"])

    assert [item["description"] for item in listed["items"]] == [
        "fatura",
        "market",
        "kira",
    ]


def test_the_listing_pages_through_a_cursor() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        for index in range(5):
            a_transaction(
                client,
                headers,
                account["id"],
                f"-{index + 1}.00",
                occurred_at=f"2026-01-0{index + 1}T09:00:00Z",
            )

        seen: list[str] = []
        page = transactions(client, headers, account["id"], limit=2)
        pages = 1
        while True:
            seen.extend(item["id"] for item in page["items"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
            page = transactions(client, headers, account["id"], limit=2, cursor=cursor)
            pages += 1

    assert pages == 3
    assert len(seen) == 5
    assert len(set(seen)) == 5


def test_the_listing_filters_by_description() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        a_transaction(client, headers, account["id"], "-500.00", description="kira")
        a_transaction(client, headers, account["id"], "-75.50", description="market")

        listed = transactions(client, headers, account["id"], q="kir")

    assert [item["description"] for item in listed["items"]] == ["kira"]


def test_the_listing_filters_by_date_range() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        for month, description in (("01", "ocak"), ("02", "şubat"), ("03", "mart")):
            a_transaction(
                client,
                headers,
                account["id"],
                "-10.00",
                occurred_at=f"2026-{month}-15T09:00:00Z",
                description=description,
            )

        listed = transactions(
            client,
            headers,
            account["id"],
            since="2026-02-01T00:00:00Z",
            until="2026-02-28T23:59:59Z",
        )

    assert [item["description"] for item in listed["items"]] == ["şubat"]
