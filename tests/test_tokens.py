"""The tokeniser: names become lowercase words, whatever the partner's naming style."""

import pytest

from padan.tokens import tokens


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # 1. separators: dots, underscores, @, brackets and = are not words
        ("voucher_url", ["voucher", "url"]),
        ("contact.email", ["contact", "email"]),
        ("items[].start_date", ["items", "start", "date"]),
        # 2. camelCase: a capital letter starts a new word
        ("firstName", ["first", "name"]),
        ("localDateTimeStart", ["local", "date", "time", "start"]),
        ("PersonName", ["person", "name"]),
        # 3. acronyms: a run of capitals is one word...
        ("ReservationID", ["reservation", "id"]),
        ("CorrelationID", ["correlation", "id"]),
        # ...until its last capital starts the next word
        ("PNRNumber", ["pnr", "number"]),
        ("HTMLUrl", ["html", "url"]),
        # 4. whole paths, attributes, filters and digits
        ("ReservationID@BookedDate", ["reservation", "id", "booked", "date"]),
        ("inputFields[id=EMAIL].value", ["input", "fields", "id", "email", "value"]),
        ("OTA_CruiseBookRQ", ["ota", "cruise", "book", "rq"]),
        ("to_e164", ["to", "e", "164"]),
    ],
)
def test_tokens(name: str, expected: list[str]) -> None:
    assert tokens(name) == expected


def test_empty_name_has_no_tokens() -> None:
    assert tokens("") == []
