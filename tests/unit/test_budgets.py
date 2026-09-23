"""Unit tests for budget input and month-boundary rules."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from kese.repositories.budgets import month_bounds
from kese.schemas.budget import BudgetCreate


def test_budget_create_keeps_decimal_limit_and_accepts_a_real_month() -> None:
    budget = BudgetCreate(
        category_id=uuid4(), month="2026-05", limit=Decimal("1250.40")
    )

    assert budget.limit == Decimal("1250.40")
    assert budget.month == "2026-05"


@pytest.mark.parametrize("month", ["2026-5", "2026-00", "2026-13", "May-2026"])
def test_budget_create_rejects_invalid_month(month: str) -> None:
    with pytest.raises(ValidationError):
        BudgetCreate(category_id=uuid4(), month=month, limit=Decimal(1))


def test_month_bounds_are_utc_and_exclusive_at_the_next_month() -> None:
    start, end = month_bounds("2026-12")

    assert start.isoformat() == "2026-12-01T00:00:00+00:00"
    assert end.isoformat() == "2027-01-01T00:00:00+00:00"
