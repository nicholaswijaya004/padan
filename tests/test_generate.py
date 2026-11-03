"""M3 step 2: the transform runtime, and a generated client run on a payload."""

from typing import Any

import pytest

from padan.generate import function_name, generate, sibling
from padan.plan import Plan, Step
from padan.runtime import (
    date_part,
    enum_map,
    minor_units_to_decimal,
    time_part,
    to_e164,
    unix_seconds_to_datetime,
)


def test_dates_and_times() -> None:
    assert date_part("2026-11-05T09:30:00+01:00") == "2026-11-05"
    assert time_part("2026-11-05T09:30:00Z") == "09:30:00"
    assert time_part("2026-11-05") is None
    assert unix_seconds_to_datetime(0) == "1970-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    ("value", "currency", "expected"),
    [
        (12345, "EUR", "123.45"),
        (1200, "JPY", "1200"),
        (12345, "KWD", "12.345"),
        ("50", None, "0.50"),
    ],
)
def test_minor_units(value: Any, currency: Any, expected: str) -> None:
    assert minor_units_to_decimal(value, currency) == expected


def test_to_e164_keeps_a_number_without_country_code() -> None:
    assert to_e164("+62 812-3456") == "+628123456"
    assert to_e164("0062 8123456") == "+628123456"
    assert to_e164("0812 3456") == "0812 3456"


def test_enum_map_refuses_an_unmapped_code() -> None:
    assert enum_map("OK", {"OK": "confirmed"}) == "confirmed"
    with pytest.raises(ValueError, match="unmapped code 'KO'"):
        enum_map("KO", {"OK": "confirmed"})


def test_names() -> None:
    assert function_name("GET /bookings/{uuid}", "response") == "from_get_bookings_uuid"
    assert sibling("a.b[].price", "currency") == "a.b[].currency"
    assert sibling("price", "currency") == "currency"


E = "GET /b/{id}"
PLAN = Plan(
    "demo",
    [
        Step(E, "response", ("ref",), "partner_booking_id", "direct"),
        Step(
            E, "response", ("state",), "status", "transform", "enum_map(OK=confirmed, KO=cancelled)"
        ),
        Step(E, "response", ("start",), "items[].start_date", "transform", "date_part"),
        Step(
            E,
            "response",
            ("total",),
            "total_price.amount",
            "transform",
            "minor_units_to_decimal(cur)",
        ),
        Step(
            E,
            "response",
            ("voucher",),
            "fulfilment[kind=voucher].value",
            "transform",
            "construct(format=pdf_url)",
        ),
        Step(
            E,
            "response",
            ("first", "last"),
            "travellers[].full_name",
            "derived",
            "first + ' ' + last",
        ),
        Step(
            E, "response", ("lead",), "travellers[].is_lead", "ask", "Which traveller is the lead?"
        ),
        Step("POST /b", "request", ("ref",), "our_booking_id", "direct"),
    ],
)


def test_a_generated_client_maps_a_payload_and_lists_its_todos() -> None:
    code = generate(PLAN, "demo.yaml")
    namespace: dict[str, Any] = {}
    exec(compile(code, "client_demo", "exec"), namespace)
    payload = {
        "ref": "B1",
        "state": "OK",
        "start": "2026-11-05T09:00:00",
        "total": 4250,
        "cur": "EUR",
        "voucher": "https://v",
    }
    assert namespace["from_get_b_id"](payload) == {
        "partner_booking_id": "B1",
        "status": "confirmed",
        "items": [{"start_date": "2026-11-05"}],
        "total_price": {"amount": "42.50"},
        "fulfilment": [{"kind": "voucher", "value": "https://v", "format": "pdf_url"}],
    }
    assert [t["target"] for t in namespace["TODOS"]] == [
        "travellers[].full_name",
        "travellers[].is_lead",
    ]
    assert "# TODO ask: travellers[].is_lead <- lead: Which traveller is the lead?" in code
    assert namespace["to_post_b"]({"our_booking_id": "P-1"}) == {"ref": "P-1"}


def test_request_steps_reverse_what_can_be_reversed_and_todo_the_rest() -> None:
    post = "POST /orders"
    plan = Plan(
        "demo",
        [
            Step(post, "request", ("ref",), "our_booking_id", "direct"),
            Step(
                post,
                "request",
                ("state",),
                "status",
                "transform",
                "enum_map(A=confirmed, B=confirmed)",
            ),
            Step(
                post,
                "request",
                ("cents",),
                "total_price.amount",
                "transform",
                "minor_units_to_decimal(cur)",
            ),
            Step(post, "request", ("when",), "items[].start_date", "transform", "date_part"),
        ],
    )
    code = generate(plan, "demo.yaml")
    namespace: dict[str, Any] = {}
    exec(compile(code, "client_demo", "exec"), namespace)
    booking = {
        "our_booking_id": "P-1",
        "status": "confirmed",
        "total_price": {"amount": "42.50", "currency": "EUR"},
        "items": [{"start_date": "2026-11-05", "activity": {"service_language": "en"}}],
    }
    assert namespace["to_post_orders"](booking) == {
        "ref": "P-1",
        "state": "A",
        "cents": 4250,
    }
    assert "# TODO transform: when <- items[].start_date: date_part cannot be reversed" in code


def test_a_list_body_comes_back_as_a_list() -> None:
    plan = Plan(
        "demo",
        [
            Step(
                "POST /items",
                "request",
                ("[].lang",),
                "items[].activity.service_language",
                "direct",
            )
        ],
    )
    namespace: dict[str, Any] = {}
    exec(compile(generate(plan, "x"), "client_demo", "exec"), namespace)
    assert namespace["to_post_items"]({"items": [{"activity": {"service_language": "en"}}]}) == [
        {"lang": "en"}
    ]
