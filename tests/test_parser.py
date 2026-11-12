"""Amount parser for the English and German Business Central formats."""

from __future__ import annotations

from decimal import Decimal

from src.trial_balance import parse_amount


def test_english_format_with_thousands_comma() -> None:
    assert parse_amount("72,893.84") == Decimal("72893.84")


def test_german_format_with_thousands_dot() -> None:
    assert parse_amount("72.893,84") == Decimal("72893.84")


def test_both_formats_are_the_same_amount() -> None:
    assert parse_amount("72,893.84") == parse_amount("72.893,84")


def test_parentheses_and_empty_values() -> None:
    assert parse_amount("(1.234,56)") == Decimal("-1234.56")
    assert parse_amount("") == Decimal(0)
    assert parse_amount(None) == Decimal(0)
    assert parse_amount("  ") == Decimal(0)
