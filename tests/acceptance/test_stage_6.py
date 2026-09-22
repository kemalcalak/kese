"""Stage 6 - importing a bank statement.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.

The statements here are generated, never real: the model is hosted, so
nothing that is not synthetic goes into this repository.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from io import BytesIO
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from httpx import Response
from openpyxl import Workbook

from kese.main import create_app

PASSWORD = "correct horse battery staple"

CSV_STATEMENT = (
    "date,description,amount\n"
    "2026-05-01,MIGROS ATASEHIR,-450.75\n"
    "2026-05-02,MAAS ODEMESI,32000.00\n"
    "2026-05-03,ECZANE,-128.40\n"
)

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


def upload(
    client: TestClient,
    headers: Headers,
    account_id: str,
    content: bytes | str = CSV_STATEMENT,
    filename: str = "ekstre.csv",
    content_type: str = "text/csv",
) -> Response:
    payload = content.encode() if isinstance(content, str) else content
    return cast(
        Response,
        client.post(
            f"/accounts/{account_id}/statements",
            files={"file": (filename, payload, content_type)},
            headers=headers,
        ),
    )


def work() -> int:
    """Run the worker once, the way the worker process does."""
    from kese.worker import run_once

    return asyncio.run(run_once())


def job(client: TestClient, headers: Headers, job_id: str) -> dict[str, Any]:
    response = client.get(f"/statements/{job_id}", headers=headers)
    assert response.status_code == 200, response.text
    return cast(dict[str, Any], response.json())


def transactions(client: TestClient, headers: Headers, account_id: str) -> list[Any]:
    response = client.get(f"/accounts/{account_id}/transactions", headers=headers)
    assert response.status_code == 200, response.text
    return cast(list[Any], response.json()["items"])


def an_xlsx_statement() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["date", "description", "amount"])
    sheet.append(["2026-06-01", "MIGROS ATASEHIR", "-450.75"])
    sheet.append(["2026-06-02", "MAAS ODEMESI", "32000.00"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_the_generator_is_deterministic() -> None:
    from kese.statements import generate_statement

    once = generate_statement(rows=5, seed=42)
    twice = generate_statement(rows=5, seed=42)
    other = generate_statement(rows=5, seed=43)

    assert once == twice
    assert once != other
    assert once.splitlines()[0] == "date,description,amount"
    assert len(once.strip().splitlines()) == 6


def test_an_upload_is_queued_and_imports_nothing_yet() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)

        response = upload(client, headers, account["id"])
        queued = job(client, headers, response.json()["id"])
        rows = transactions(client, headers, account["id"])

    assert response.status_code == 202
    assert queued["status"] == "pending"
    assert rows == []


def test_the_worker_imports_the_rows() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        queued = upload(client, headers, account["id"]).json()

        processed = work()

        finished = job(client, headers, queued["id"])
        rows = transactions(client, headers, account["id"])

    assert processed == 1
    assert finished["status"] == "done"
    assert finished["imported"] == 3
    assert finished["duplicates"] == 0
    assert {Decimal(str(row["amount"])) for row in rows} == {
        Decimal("-450.75"),
        Decimal("32000.00"),
        Decimal("-128.40"),
    }


def test_the_same_statement_twice_imports_nothing_twice() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        upload(client, headers, account["id"])
        work()

        second = upload(client, headers, account["id"]).json()
        work()

        finished = job(client, headers, second["id"])
        rows = transactions(client, headers, account["id"])

    assert finished["status"] == "done"
    assert finished["imported"] == 0
    assert finished["duplicates"] == 3
    assert len(rows) == 3


def test_an_imported_row_obeys_the_rules() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        category = client.post(
            "/categories", json={"name": "Market"}, headers=headers
        ).json()
        client.post(
            "/rules",
            json={"pattern": "migros", "category_id": category["id"], "priority": 10},
            headers=headers,
        )

        upload(client, headers, account["id"])
        work()

        rows = transactions(client, headers, account["id"])

    categorised = {
        row["description"]: row["category_id"] for row in rows if row["category_id"]
    }
    assert categorised == {"MIGROS ATASEHIR": category["id"]}


def test_an_xlsx_statement_imports_too() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        queued = upload(
            client,
            headers,
            account["id"],
            content=an_xlsx_statement(),
            filename="ekstre.xlsx",
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        ).json()

        work()

        finished = job(client, headers, queued["id"])

    assert finished["status"] == "done"
    assert finished["imported"] == 2


def test_a_broken_row_fails_its_row_and_not_the_job() -> None:
    broken = (
        "date,description,amount\n"
        "2026-07-01,MIGROS,-10.00\n"
        "not-a-date,ECZANE,-5.00\n"
        "2026-07-03,SU FATURASI,-90.25\n"
    )

    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        queued = upload(client, headers, account["id"], content=broken).json()

        work()

        finished = job(client, headers, queued["id"])
        rows = transactions(client, headers, account["id"])

    assert finished["status"] == "done"
    assert finished["imported"] == 2
    assert finished["failed"] == 1
    assert len(rows) == 2


def test_an_unsupported_file_is_refused() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)

        response = upload(
            client,
            headers,
            account["id"],
            content="hello",
            filename="ekstre.txt",
            content_type="text/plain",
        )

    assert response.status_code == 415


def test_a_stranger_can_neither_upload_nor_read_the_job() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        account = an_account(client, headers)
        queued = upload(client, headers, account["id"]).json()

        stranger = a_user(client)
        uploading = upload(client, stranger, account["id"])
        reading = client.get(f"/statements/{queued['id']}", headers=stranger)

    assert uploading.status_code == 404
    assert reading.status_code == 404


def test_the_worker_takes_one_job_at_a_time() -> None:
    with TestClient(create_app()) as client:
        headers = a_user(client)
        first = an_account(client, headers)
        second = an_account(client, headers)
        upload(client, headers, first["id"])
        upload(client, headers, second["id"])

        processed = work()
        left = client.get("/statements", headers=headers).json()

    assert processed == 1
    assert sorted(item["status"] for item in left) == ["done", "pending"]
