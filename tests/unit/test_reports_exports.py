"""Unit tests for report and export calculations."""

from datetime import UTC, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook

from kese.api.exports import csv_chunks
from kese.services.exports import build_xlsx
from kese.services.reports import export_range, parse_month


def test_month_and_export_boundaries_are_utc() -> None:
    assert parse_month("2026-05").isoformat() == "2026-05-01"
    assert export_range("2026-05-01", "2026-05-31") == (
        datetime(2026, 5, 1, tzinfo=UTC),
        datetime(2026, 6, 1, tzinfo=UTC),
    )


def test_csv_chunks_have_decimal_text_and_expected_header() -> None:
    rows = [
        (
            datetime(2026, 5, 2, 23, 0, tzinfo=UTC),
            "Vadesiz",
            "MIGROS",
            "Market",
            Decimal("-450.75"),
        )
    ]
    assert "".join(csv_chunks(rows)) == (
        "date,account,description,category,amount\r\n"
        "2026-05-02,Vadesiz,MIGROS,Market,-450.75\r\n"
    )


def test_xlsx_export_writes_amount_as_a_numeric_cell() -> None:
    rows = [
        (
            datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
            "Vadesiz",
            "MIGROS",
            None,
            Decimal("-450.75"),
        )
    ]
    sheet = load_workbook(BytesIO(build_xlsx(rows))).active
    assert sheet is not None
    assert sheet.cell(row=1, column=5).value == "amount"
    assert sheet.cell(row=2, column=5).value == Decimal("-450.75")
