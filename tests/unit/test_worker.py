"""Unit tests for statement worker parsing and duplicate keys."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook

from kese.worker import _fingerprint, parse_statement


def test_parse_csv_preserves_decimal_and_utc_datetime() -> None:
    rows = list(
        parse_statement(
            "statement.csv",
            b"date,description,amount\n2026-05-01T03:00:00+03:00,SHOP,-10.50\n",
        )
    )

    assert rows == [(rows[0][0], "SHOP", Decimal("-10.50"))]
    assert rows[0][0].isoformat() == "2026-05-01T00:00:00+00:00"


def test_parse_xlsx_maps_the_statement_columns() -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["date", "description", "amount"])
    sheet.append(["2026-06-01", "SHOP", "12.30"])
    buffer = BytesIO()
    workbook.save(buffer)

    rows = list(parse_statement("statement.xlsx", buffer.getvalue()))

    assert rows[0][1:] == ("SHOP", Decimal("12.30"))
    assert rows[0][0].tzinfo is not None


def test_fingerprint_is_stable_for_the_same_row() -> None:
    rows = list(
        parse_statement(
            "statement.csv", b"date,description,amount\n2026-05-01,SHOP,1.20\n"
        )
    )

    first = _fingerprint("account", *rows[0])
    second = _fingerprint("account", *rows[0])

    assert first == second
