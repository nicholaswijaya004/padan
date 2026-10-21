from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from padan.schema import Booking, Contact, CustomField, Fulfilment, Item, Money, Traveller


def valid_booking(**overrides: Any) -> dict[str, Any]:
    """A minimal valid activity booking; each test overrides only what it is testing."""
    data: dict[str, Any] = {
        "our_booking_id": "padan-1",
        "status": "confirmed",
        "contact": {"email": "ana@example.com"},
        "travellers": [{"given_name": "Ana", "is_lead": True}],
        "items": [{"start_date": "2026-11-02", "activity": {}}],
    }
    data.update(overrides)
    return data


# --- Money ---------------------------------------------------------------------------------


def test_money_float_point_one_becomes_exact_decimal() -> None:
    # P1: Pydantic converts the float via its shortest repr, so 0.1 arrives as Decimal("0.1").
    assert Money.model_validate({"amount": 0.1, "currency": "EUR"}).amount == Decimal("0.1")


def test_money_float_arithmetic_error_survives_into_decimal() -> None:
    # P2: the float is already wrong before Pydantic sees it; Decimal faithfully keeps the error.
    # Lesson: partner amounts must reach the schema as strings or Decimals, never as floats.
    assert Money.model_validate({"amount": 0.1 + 0.2, "currency": "EUR"}).amount == Decimal(
        "0.30000000000000004"
    )


def test_money_string_amount_is_exact() -> None:
    assert Money.model_validate({"amount": "0.30", "currency": "EUR"}).amount == Decimal("0.30")


def test_money_rejects_lowercase_currency() -> None:
    # P3: the pattern ^[A-Z]{3}$ is case-sensitive; normalising "eur" is the mapper's job.
    with pytest.raises(ValidationError):
        Money.model_validate({"amount": "1", "currency": "eur"})


# --- Dates ---------------------------------------------------------------------------------


def test_start_date_accepts_plain_date() -> None:
    assert Booking.model_validate(valid_booking()).items[0].start_date == date(2026, 11, 2)


def test_start_date_rejects_datetime_with_time_and_timezone() -> None:
    # P4: a date field refuses a datetime that carries a non-midnight time: no silent truncation.
    with pytest.raises(ValidationError):
        Item.model_validate({"start_date": "2026-10-09T14:00:00+07:00", "activity": {}})


def test_start_date_rejects_impossible_date() -> None:
    # P5: Hotelbeds' example "2016-04-31" (April has 30 days) is rejected, not silently fixed.
    with pytest.raises(ValidationError):
        Item.model_validate({"start_date": "2016-04-31", "activity": {}})


# --- Traveller names (J1) ------------------------------------------------------------------


def test_traveller_with_no_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Traveller(is_lead=True)


def test_traveller_with_empty_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Traveller(given_name="", is_lead=True)


def test_single_name_traveller_is_accepted() -> None:
    traveller = Traveller(given_name="Sukarno", is_lead=True)
    assert traveller.family_name is None


def test_full_name_only_traveller_is_accepted() -> None:
    # Headout sends one NAME field; it maps to full_name without splitting.
    traveller = Traveller(full_name="Siti Nurhaliza", is_lead=True)
    assert traveller.given_name is None


# --- Booking invariants --------------------------------------------------------------------


def test_minimal_activity_booking_is_valid() -> None:
    Booking.model_validate(valid_booking())


def test_booking_without_lead_traveller_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Booking.model_validate(valid_booking(travellers=[{"given_name": "Ana", "is_lead": False}]))


def test_booking_with_two_lead_travellers_is_rejected() -> None:
    two_leads = [{"given_name": "Ana", "is_lead": True}, {"given_name": "Budi", "is_lead": True}]
    with pytest.raises(ValidationError):
        Booking.model_validate(valid_booking(travellers=two_leads))


def test_item_with_both_activity_and_cruise_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Item.model_validate({"start_date": "2026-11-02", "activity": {}, "cruise": {}})


def test_item_with_neither_activity_nor_cruise_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Item.model_validate({"start_date": "2026-11-02"})


def test_cruise_booking_is_valid() -> None:
    cabin = {"start_date": "2023-01-30", "product_id": "CS21711JUNKTN", "option_id": "A"}
    booking = Booking.model_validate(valid_booking(items=[cabin | {"cruise": {"deck": "1"}}]))
    assert booking.items[0].cruise is not None
    assert booking.items[0].option_id == "A"


# --- Schema v3: items ------------------------------------------------------------------------


def test_booking_without_items_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Booking.model_validate(valid_booking(items=[]))


def test_one_booking_can_hold_several_activities() -> None:
    # Hotelbeds: one booking, activities[] on different dates; each becomes an item.
    two = [
        {"product_id": "E-E10-PARIS", "start_date": "2026-11-02", "activity": {}},
        {"product_id": "E-E10-LOUVRE", "start_date": "2026-11-03", "activity": {}},
    ]
    booking = Booking.model_validate(valid_booking(items=two))
    assert [item.start_date.day for item in booking.items] == [2, 3]


def test_balance_due_date_is_booking_level_and_critical() -> None:
    extra = Booking.model_fields["balance_due_date"].json_schema_extra
    assert isinstance(extra, dict)
    assert extra["critical"] is True


# --- Metadata ------------------------------------------------------------------------------


def test_critical_fields_are_marked() -> None:
    extra = Booking.model_fields["total_price"].json_schema_extra
    assert isinstance(extra, dict)
    assert extra["critical"] is True


def test_our_booking_id_is_sourced_by_us() -> None:
    extra = Booking.model_fields["our_booking_id"].json_schema_extra
    assert isinstance(extra, dict)
    assert extra["source"] == "ours"


# --- Schema v1: custom fields and slot ------------------------------------------------------


def test_custom_fields_default_to_empty() -> None:
    booking = Booking.model_validate(valid_booking())
    assert booking.custom_fields == []
    assert booking.travellers[0].custom_fields == []


def test_custom_field_requires_field_id() -> None:
    with pytest.raises(ValidationError):
        CustomField.model_validate({"value": "Hotel Indonesia"})


def test_booking_level_custom_field_and_slot_are_kept() -> None:
    booking = Booking.model_validate(
        valid_booking(
            custom_fields=[{"field_id": "PICKUP_LOCATION", "value": "Hotel Indonesia"}],
            items=[{"start_date": "2026-11-02", "activity": {"slot_id": "inv-123"}}],
        )
    )
    assert booking.custom_fields[0].field_id == "PICKUP_LOCATION"
    assert booking.items[0].activity is not None
    assert booking.items[0].activity.slot_id == "inv-123"


# --- Schema v2: fulfilment, hold, net price, split contact ---------------------------------


def test_fulfilment_keeps_qr_codes_and_urls_apart() -> None:
    booking = Booking.model_validate(
        valid_booking(
            fulfilment=[
                {"kind": "voucher", "format": "pdf_url", "value": "https://x.test/v.pdf"},
                {"kind": "ticket", "format": "qrcode", "value": "!1|El3f0w", "partner_id": "t-1"},
            ]
        )
    )
    assert [f.format for f in booking.fulfilment] == ["pdf_url", "qrcode"]


def test_fulfilment_rejects_unknown_kind() -> None:
    with pytest.raises(ValidationError):
        Fulfilment.model_validate({"kind": "passport", "format": "text", "value": "X1"})


def test_on_hold_booking_keeps_its_expiry() -> None:
    booking = Booking.model_validate(
        valid_booking(status="on_hold", hold_expires_at="2026-11-01T10:00:00Z")
    )
    assert booking.status == "on_hold"
    assert booking.hold_expires_at is not None


def test_gross_and_net_price_are_separate() -> None:
    booking = Booking.model_validate(
        valid_booking(
            total_price={"amount": "120.00", "currency": "USD"},
            net_price={"amount": "100.00", "currency": "USD"},
        )
    )
    assert booking.total_price is not None and booking.net_price is not None
    assert booking.total_price.amount - booking.net_price.amount == Decimal("20.00")


def test_contact_name_can_be_split() -> None:
    contact = Contact.model_validate({"given_name": "Ana", "family_name": "Lim"})
    assert contact.full_name is None


def test_nationality_must_be_alpha_2() -> None:
    with pytest.raises(ValidationError):
        Traveller.model_validate({"given_name": "Ana", "is_lead": True, "nationality": "IDN"})


def test_new_critical_fields_are_marked() -> None:
    for name in ("net_price", "hold_expires_at", "fulfilment"):
        extra = Booking.model_fields[name].json_schema_extra
        assert isinstance(extra, dict)
        assert extra["critical"] is True, name


# --- Schema v2.1: redemption time -----------------------------------------------------------


def test_redemption_time_is_kept_per_booking_and_per_ticket() -> None:
    booking = Booking.model_validate(
        valid_booking(
            redeemed_at="2026-11-02T09:15:00Z",
            fulfilment=[
                {
                    "kind": "ticket",
                    "format": "qrcode",
                    "value": "!1|El3f0w",
                    "redeemed_at": "2026-11-02T09:15:00Z",
                },
                {"kind": "ticket", "format": "qrcode", "value": "!1|Xk9a2p"},
            ],
        )
    )
    assert booking.redeemed_at is not None
    assert [f.redeemed_at is not None for f in booking.fulfilment] == [True, False]
