"""Stage 7 - exchange rates from the central bank.

Written by hand before the stage and never edited: it states what the stage
has to do. It needs the compose database up and the migrations applied.

Nothing here touches the network: every request to tcmb.gov.tr is mocked, so
the tests say what the code does with an answer, a silence and a refusal.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, cast
from uuid import uuid4

import httpx
import respx
from fastapi.testclient import TestClient
from httpx import Response

from kese.main import create_app

PASSWORD = "correct horse battery staple"

Headers = dict[str, str]

#: The shape tcmb.gov.tr answers with, trimmed to what matters here. JPY is
#: quoted per 100 units, which is the trap in this format.
BULLETIN = """<?xml version="1.0" encoding="UTF-8"?>
<Tarih_Date Tarih="04.05.2026" Date="05/04/2026" Bulten_No="2026/85">
  <Currency CrossOrder="0" Kod="USD" CurrencyCode="USD">
    <Unit>1</Unit>
    <CurrencyName>US DOLLAR</CurrencyName>
    <ForexBuying>41.1234</ForexBuying>
    <ForexSelling>41.2345</ForexSelling>
  </Currency>
  <Currency CrossOrder="9" Kod="JPY" CurrencyCode="JPY">
    <Unit>100</Unit>
    <CurrencyName>JAPENESE YEN</CurrencyName>
    <ForexBuying>26.5000</ForexBuying>
    <ForexSelling>26.7000</ForexSelling>
  </Currency>
</Tarih_Date>
"""

TODAY_URL = "https://www.tcmb.gov.tr/kurlar/202605/04052026.xml"
FRIDAY_URL = "https://www.tcmb.gov.tr/kurlar/202605/01052026.xml"


def an_email() -> str:
    return f"user-{uuid4().hex}@example.com"


def a_user(client: TestClient) -> Headers:
    email = an_email()
    client.post("/auth/register", json={"email": email, "password": PASSWORD})
    tokens = client.post(
        "/auth/login", json={"email": email, "password": PASSWORD}
    ).json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def rate(
    client: TestClient, headers: Headers, code: str, on: str = "2026-05-04"
) -> Response:
    return cast(
        Response, client.get(f"/rates/{code}", params={"on": on}, headers=headers)
    )


def body(response: Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


@respx.mock
def test_a_rate_comes_from_the_bulletin() -> None:
    respx.get(TODAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "USD")

    assert response.status_code == 200
    assert body(response)["code"] == "USD"
    assert Decimal(str(body(response)["rate"])) == Decimal("41.2345")


@respx.mock
def test_a_rate_quoted_per_hundred_is_divided() -> None:
    respx.get(TODAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "JPY")

    assert response.status_code == 200
    assert Decimal(str(body(response)["rate"])) == Decimal("0.267")


@respx.mock
def test_the_bulletin_is_fetched_once_and_then_cached() -> None:
    route = respx.get(TODAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        headers = a_user(client)
        first = rate(client, headers, "USD")
        second = rate(client, headers, "USD")

    assert first.status_code == 200
    assert second.status_code == 200
    assert route.call_count == 1


@respx.mock
def test_a_currency_the_bulletin_does_not_carry_is_404() -> None:
    respx.get(TODAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "SEK")

    assert response.status_code == 404


@respx.mock
def test_a_day_with_no_bulletin_falls_back_to_the_last_one() -> None:
    respx.get(TODAY_URL).mock(return_value=httpx.Response(404))
    respx.get("https://www.tcmb.gov.tr/kurlar/202605/03052026.xml").mock(
        return_value=httpx.Response(404)
    )
    respx.get("https://www.tcmb.gov.tr/kurlar/202605/02052026.xml").mock(
        return_value=httpx.Response(404)
    )
    respx.get(FRIDAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "USD")

    assert response.status_code == 200
    assert body(response)["rate_date"] == "2026-05-01"


@respx.mock
def test_a_timeout_is_retried_before_it_is_believed() -> None:
    route = respx.get(TODAY_URL).mock(
        side_effect=[
            httpx.TimeoutException("too slow"),
            httpx.Response(200, text=BULLETIN),
        ]
    )

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "USD")

    assert response.status_code == 200
    assert route.call_count == 2


@respx.mock
def test_a_bank_that_never_answers_is_reported_not_invented() -> None:
    respx.get(TODAY_URL).mock(side_effect=httpx.TimeoutException("too slow"))

    with TestClient(create_app()) as client:
        response = rate(client, a_user(client), "USD")

    assert response.status_code == 503


@respx.mock
def test_conversion_multiplies_by_the_rate() -> None:
    respx.get(TODAY_URL).mock(return_value=httpx.Response(200, text=BULLETIN))

    with TestClient(create_app()) as client:
        response = client.get(
            "/convert",
            params={
                "amount": "100.00",
                "source": "USD",
                "target": "TRY",
                "on": "2026-05-04",
            },
            headers=a_user(client),
        )

    assert response.status_code == 200
    assert Decimal(str(body(response)["converted"])) == Decimal("4123.45")


def test_rates_need_a_token() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/rates/USD", params={"on": "2026-05-04"})

    assert response.status_code == 401
