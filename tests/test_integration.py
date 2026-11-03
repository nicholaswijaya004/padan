"""Day 23: padan's own fields on a client's record, and casting requests to the partner's types."""

from typing import Any

import pytest
from pydantic import ValidationError

from padan.generate import generate
from padan.integration import choose_lead, full_name, to_booking
from padan.plan import Plan, Step
from padan.runtime import cast

RECORD: dict[str, Any] = {
    "status": "confirmed",
    "contact": {"full_name": "Ben  Lima"},
    "travellers": [
        {"given_name": "Ana", "family_name": "Lima"},
        {"given_name": "Ben", "family_name": "Lima"},
    ],
    "items": [{"start_date": "2026-12-01"}],
    "our_booking_id": "echoed-ref",
}


def test_full_name_matches_however_it_is_written() -> None:
    assert full_name({"given_name": "Ben", "family_name": "LIMA"}) == full_name(
        {"full_name": "ben  lima"}
    )


def test_the_lead_is_the_traveller_matching_the_contact_else_the_first() -> None:
    record: dict[str, Any] = {
        "contact": {"full_name": "Ben Lima"},
        "travellers": [{"given_name": "Ana"}, {"full_name": "Ben Lima"}],
    }
    assert choose_lead(record) == "lead: the traveller matching the contact"
    assert [t["is_lead"] for t in record["travellers"]] == [False, True]
    record = {
        "contact": {"full_name": "Someone Else"},
        "travellers": [{"given_name": "Ana"}, {"given_name": "Ben"}],
    }
    assert choose_lead(record) == "lead: the first traveller"
    assert [t["is_lead"] for t in record["travellers"]] == [True, False]


def test_a_lead_given_by_the_partner_is_kept() -> None:
    record: dict[str, Any] = {
        "travellers": [{"given_name": "Ana"}, {"given_name": "Ben", "is_lead": True}]
    }
    assert choose_lead(record) == "lead: given by the partner"
    assert [t["is_lead"] for t in record["travellers"]] == [False, True]


def test_to_booking_adds_padans_fields_and_says_so() -> None:
    booking, notes = to_booking(RECORD, our_booking_id="PADAN-1")
    assert booking.our_booking_id == "PADAN-1"
    assert booking.items[0].activity is not None
    assert [t.is_lead for t in booking.travellers] == [False, True]
    assert notes == [
        "our_booking_id: the partner echoes 'echoed-ref'; padan's own ID is used",
        "item: vertical set to activity",
        "lead: the traveller matching the contact",
    ]
    assert RECORD["our_booking_id"] == "echoed-ref"  # the client's record is not changed


def test_to_booking_still_refuses_what_only_the_partner_can_give() -> None:
    with pytest.raises(ValidationError, match="status"):
        to_booking({k: v for k, v in RECORD.items() if k != "status"}, our_booking_id="PADAN-1")


@pytest.mark.parametrize(
    ("values", "kind", "expected"),
    [
        (["42", "OPT-1", True], "integer", [42, "OPT-1", True]),
        (["120.50"], "number", [120.5]),
        (["true", "false", "yes"], "boolean", [True, False, "yes"]),
        (["42"], "string", ["42"]),
    ],
)
def test_cast(values: list[Any], kind: str, expected: list[Any]) -> None:
    assert cast(values, kind) == expected


def test_requests_are_cast_by_the_partners_field_types() -> None:
    plan = Plan("demo", [Step("POST /b", "request", ("option",), "items[].option_id", "direct")])
    code = generate(plan, "x", {("POST /b", "request", "option"): "integer|null"})
    assert "cast(get(booking, 'items[].option_id'), 'integer')" in code
    namespace: dict[str, Any] = {}
    exec(compile(code, "client_demo", "exec"), namespace)
    assert namespace["to_post_b"]({"items": [{"option_id": "2002"}]}) == {"option": 2002}
