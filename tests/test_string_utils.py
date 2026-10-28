"""Tests de normalización léxica."""

from __future__ import annotations

import pytest

from etl.transformers.string_utils import clean_str, strip_periods


@pytest.mark.parametrize("input_str, expected", [
    ("  MAÍZ ", "maiz"),
    ("Caña de Azúcar", "cana de azucar"),
    ("Cebada  Cervecera", "cebada cervecera"),
    ("TRIGO CANDEAL", "trigo candeal"),
    ("J.B.ALBERDI", "j.b.alberdi"),
])
def test_clean_str_basic(input_str: str, expected: str) -> None:
    assert clean_str(input_str) == expected


@pytest.mark.parametrize("input_str", [
    "  MAÍZ ", "Cebada  Cervecera", "TRIGO CANDEAL", "Caña de Azúcar"
])
def test_clean_str_idempotent(input_str: str) -> None:
    assert clean_str(clean_str(input_str)) == clean_str(input_str)


def test_clean_str_non_string() -> None:
    assert clean_str(None) is None
    assert clean_str(123) == 123


@pytest.mark.parametrize("input_str, expected", [
    ("leandro n. alem", "leandro n alem"),
    ("j.b.alberdi", "j b alberdi"),
    ("gral. san martin", "gral san martin"),
])
def test_strip_periods(input_str: str, expected: str) -> None:
    assert strip_periods(input_str) == expected