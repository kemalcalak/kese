"""End-to-end statement import coverage against PostgreSQL."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from io import BytesIO
from typing import Any, cast
from uuid import uuid4

from fastapi.testclient import TestClient
from openpyxl import Workbook

from kese.main import create_app
from kese.worker import run_once

PASSWORD = "correct horse battery staple"
CSV_CONTENT = (
    "date,description,amount\n"
    "2026-08-01,MIGROS,-10.00\n"
    "not-a-date,BROKEN,-5.00\n"
    "2026-08-03,MIGROS,-10.00\n"
)


def _user(client: TestClient) -> dict[str, str]:
    email = f"integration-{uuid4().hex}@example.com"
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    token = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _account(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/accounts", json={"name": "Integration", "currency": "TRY"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["id"])


def _xlsx() -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["date", "description", "amount"])
    sheet.append(["2026-08-10", "BOOKS", "12.50"])
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _process_until_finished(
    client: TestClient, headers: dict[str, str], statement_id: str
) -> dict[str, Any]:
    for _ in range(20):
        asyncio.run(run_once())
        status = client.get(f"/statements/{statement_id}", headers=headers).json()
        if status["status"] != "pending":
            return cast(dict[str, Any], status)
    raise AssertionError("statement job remained pending")


def test_statement_upload_worker_status_dedup_and_rules() -> None:
    with TestClient(create_app()) as client:
        headers = _user(client)
        account_id = _account(client, headers)
        category = client.post("/categories", json={"name": "Market"}, headers=headers)
        assert category.status_code == 201, category.text
        rule = client.post(
            "/rules",
            json={
                "pattern": "migros",
                "category_id": category.json()["id"],
                "priority": 1,
            },
            headers=headers,
        )
        assert rule.status_code == 201, rule.text

        upload = client.post(
            f"/accounts/{account_id}/statements",
            files={"file": ("statement.csv", CSV_CONTENT.encode(), "text/csv")},
            headers=headers,
        )
        assert upload.status_code == 202, upload.text
        statement_id = upload.json()["id"]
        assert (
            client.get(f"/statements/{statement_id}", headers=headers).json()["status"]
            == "pending"
        )

        finished = _process_until_finished(client, headers, statement_id)
        assert finished["status"] == "done"
        assert finished["imported"] == 2
        assert finished["duplicates"] == 0
        assert finished["failed"] == 1

        rows = client.get(
            f"/accounts/{account_id}/transactions", headers=headers
        ).json()["items"]
        assert len(rows) == 2
        assert {Decimal(str(row["amount"])) for row in rows} == {Decimal("-10.00")}
        assert all(row["category_id"] == category.json()["id"] for row in rows)

        duplicate = client.post(
            f"/accounts/{account_id}/statements",
            files={"file": ("statement.csv", CSV_CONTENT.encode(), "text/csv")},
            headers=headers,
        )
        assert duplicate.status_code == 202, duplicate.text
        duplicate_status = _process_until_finished(
            client, headers, duplicate.json()["id"]
        )
        assert duplicate_status["imported"] == 0
        assert duplicate_status["duplicates"] == 2
        assert duplicate_status["failed"] == 1

        xlsx_upload = client.post(
            f"/accounts/{account_id}/statements",
            files={
                "file": (
                    "statement.xlsx",
                    _xlsx(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=headers,
        )
        assert xlsx_upload.status_code == 202, xlsx_upload.text
        xlsx_status = _process_until_finished(client, headers, xlsx_upload.json()["id"])
        assert xlsx_status["imported"] == 1

        assert client.get("/statements", headers=headers).status_code == 200

        stranger = _user(client)
        assert (
            client.get(f"/statements/{statement_id}", headers=stranger).status_code
            == 404
        )


def test_statement_upload_rejects_unsupported_files() -> None:
    with TestClient(create_app()) as client:
        headers = _user(client)
        account_id = _account(client, headers)
        response = client.post(
            f"/accounts/{account_id}/statements",
            files={"file": ("statement.txt", b"nope", "text/plain")},
            headers=headers,
        )

    assert response.status_code == 415
