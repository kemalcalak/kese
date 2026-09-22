"""Deterministic synthetic bank-statement data for tests and development.

This module creates fictional statements only. It never reads, imports, or
represents a real bank statement.
"""

from __future__ import annotations

import csv
import random
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

_DESCRIPTIONS = (
    "COFFEE, KADIKOY",
    'BOOKS "DUNE"',
    "GROCERY MARKET",
    "PUBLIC TRANSPORT",
    "SYNTHETIC PAYROLL",
)


def generate_statement(rows: int, seed: int) -> str:
    """Return a deterministic CSV containing fictional statement rows.

    The generated data is synthetic and is not read from or based on a real
    bank statement. A local random generator keeps the result stable for the
    same ``rows`` and ``seed`` without changing process-global random state.
    """
    if rows < 0:
        raise ValueError("rows must be non-negative")

    generator = random.Random(seed)
    output = StringIO(newline="")
    csv_writer = csv.writer(output, lineterminator="\n")
    csv_writer.writerow(("date", "description", "amount"))

    start_date = date(2026, 1, 1)
    for row_number in range(rows):
        amount_cents = generator.randint(100, 500_000)
        if generator.choice((True, False)):
            amount_cents *= -1
        csv_writer.writerow(
            (
                start_date + timedelta(days=row_number),
                generator.choice(_DESCRIPTIONS),
                f"{Decimal(amount_cents) / Decimal(100):.2f}",
            )
        )

    return output.getvalue()
