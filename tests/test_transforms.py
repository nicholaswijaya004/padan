"""Transform vocabulary: parsing, and equality that ignores the order of keyword arguments."""

import pytest

from padan.transforms import Transform, parse_transform


def test_a_bare_name() -> None:
    assert parse_transform("date_part") == Transform("date_part")


def test_keyword_arguments_ignore_order_and_spacing() -> None:
    a = parse_transform("enum_map(ADULT=adult, CHILD=child)")
    b = parse_transform(" enum_map( CHILD = child,ADULT=adult ) ")
    assert a == b == Transform("enum_map", (("ADULT", "adult"), ("CHILD", "child")))


def test_one_different_value_is_a_different_transform() -> None:
    assert parse_transform("enum_map(PENDING=pending)") != parse_transform(
        "enum_map(PENDING=confirmed)"
    )


def test_a_positional_argument_has_an_empty_key() -> None:
    assert parse_transform("minor_units_to_decimal(currencyCode)") == Transform(
        "minor_units_to_decimal", (("", "currencyCode"),)
    )


@pytest.mark.parametrize(
    "text",
    [
        "add_days(checkIn, nights)",  # not in the vocabulary
        "unix_seconds_to_datetime(+1h) while status=UNCAPTURED",  # a recipe, not a call
        "enum_map(ADULT=adult",  # unclosed
        "enum_map(ADULT=adult, ADULT=child)",  # one code mapped twice
    ],
)
def test_rejected(text: str) -> None:
    with pytest.raises(ValueError):
        parse_transform(text)
