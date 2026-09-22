"""Unit tests for the synthetic statement generator."""

from __future__ import annotations

import csv
import io

from kese.statements import generate_statement


def test_generator_returns_a_valid_csv_with_expected_header_and_rows() -> None:
    statement = generate_statement(rows=3, seed=42)

    parsed = list(csv.reader(io.StringIO(statement, newline="")))

    assert parsed[0] == ["date", "description", "amount"]
    assert len(parsed) == 4
    assert all(len(row) == 3 for row in parsed)


def test_generator_is_deterministic_for_the_same_inputs() -> None:
    assert generate_statement(rows=5, seed=42) == generate_statement(rows=5, seed=42)


def test_generator_changes_output_for_a_different_seed() -> None:
    assert generate_statement(rows=5, seed=42) != generate_statement(rows=5, seed=43)


def test_generator_returns_only_the_header_for_zero_rows() -> None:
    statement = generate_statement(rows=0, seed=42)

    assert statement == "date,description,amount\n"
