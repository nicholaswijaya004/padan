"""R4: enum_map from documented values. You write enum_map_from()."""

from padan.enums import ENUM_VALUES, enum_map_from
from padan.transforms import parse_transform

TYPE = "travellers[].traveller_type"
FORMAT = "fulfilment[kind=voucher].format"


def test_enum_values_come_from_the_schema() -> None:
    assert ENUM_VALUES["travellers[].traveller_type"] >= {"adult", "child", "senior"}
    assert "qrcode" in ENUM_VALUES["fulfilment[].format"]
    assert set(ENUM_VALUES) == {
        "status",
        "travellers[].traveller_type",
        "fulfilment[].kind",
        "fulfilment[].format",
    }


def test_codes_in_backticks_map_by_name() -> None:
    evidence = "Pricing category for this customer (e.g., `ADULT`, `CHILD`, `SENIOR`)."
    assert enum_map_from(evidence, TYPE) == "enum_map(ADULT=adult, CHILD=child, SENIOR=senior)"


def test_the_result_is_a_valid_transform() -> None:
    evidence = "possible values are: `QRCODE` generate it yourself. `PDF_URL` a link to a PDF."
    result = enum_map_from(evidence, FORMAT)
    assert result is not None
    assert parse_transform(result) == parse_transform("enum_map(PDF_URL=pdf_url, QRCODE=qrcode)")


def test_a_code_mentioned_twice_is_listed_once() -> None:
    evidence = "`ADULT` or `CHILD`; a `CHILD` needs an `ADULT`."
    assert enum_map_from(evidence, TYPE) == "enum_map(ADULT=adult, CHILD=child)"


def test_lowercase_words_in_backticks_are_not_codes() -> None:
    evidence = "`ADULT` or `CHILD`, as in the `tickets` array."
    assert enum_map_from(evidence, TYPE) == "enum_map(ADULT=adult, CHILD=child)"


def test_one_code_without_a_value_means_no_table() -> None:
    # APPLE_WALLET_URL is a real value with no same-named match: a partial table would drop it
    evidence = "`PDF_URL`, `QRCODE` or `APPLE_WALLET_URL`."
    assert enum_map_from(evidence, FORMAT) is None


def test_no_documented_codes_means_no_table() -> None:
    assert enum_map_from("[no description; example: ADULT]", TYPE) is None
