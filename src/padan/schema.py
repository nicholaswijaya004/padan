"""Canonical booking schema v2: the target every partner field maps onto (ADR-001)."""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


def meta(
    description: str, *, default: Any = ..., source: str = "partner", critical: bool = False
) -> Any:
    """A Field with padan's metadata: where the value comes from, and whether errors are costly.

    Without `default` the field is required; pass default=None for optional fields.
    """
    return Field(
        default, description=description, json_schema_extra={"source": source, "critical": critical}
    )


class Money(BaseModel):
    amount: Decimal = meta(
        "Amount in major units of `currency` (e.g. 12.50 EUR, not 1250).", critical=True
    )
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 code, uppercase.")


class CustomField(BaseModel):
    """A partner-specific booking question and its answer (e.g. pickup location, language)."""

    field_id: str = meta("Partner's identifier for the question, e.g. PICKUP_LOCATION.")
    label: str | None = meta(
        "Human-readable question text, if the partner gives one.", default=None
    )
    value: str | None = meta("The answer given for this booking.", default=None)


class Fulfilment(BaseModel):
    """One document the customer uses to get in: the booking's voucher or a single ticket."""

    kind: Literal["voucher", "ticket"] = meta(
        "voucher covers the whole booking; ticket is one entry credential."
    )
    format: Literal["pdf_url", "html_url", "wallet_url", "qrcode", "barcode", "text", "other"] = (
        meta("How it is delivered; decides whether value is a URL or a code.")
    )
    value: str = meta("The URL, or the code itself (QR payload, barcode, text code).")
    partner_id: str | None = meta("Partner's identifier for this document, if any.", default=None)


class Traveller(BaseModel):
    given_name: str | None = meta("Given name(s) as on the travel document.", default=None)
    family_name: str | None = meta("Family name; None for single-name travellers.", default=None)
    full_name: str | None = meta(
        "Full name when the partner does not split it (e.g. Headout NAME).", default=None
    )
    traveller_type: (
        Literal["adult", "child", "infant", "youth", "senior", "student", "other"] | None
    ) = meta("Pricing category of this traveller.", default=None)
    age: int | None = meta("Age in years at time of travel.", default=None)
    date_of_birth: date | None = meta("Date of birth, e.g. for cruise manifests.", default=None)
    nationality: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{2}$",
        description="ISO 3166-1 alpha-2 country code, uppercase.",
        json_schema_extra={"source": "partner", "critical": False},
    )
    is_lead: bool = meta("True for the lead traveller of the booking.")
    custom_fields: list[CustomField] = meta(
        "Partner-specific questions answered per traveller.", default=[]
    )

    @model_validator(mode="after")
    def has_a_name(self) -> "Traveller":
        if not self.given_name and not self.full_name:
            raise ValueError("traveller needs given_name or full_name")
        return self


class Contact(BaseModel):
    """The person who made and pays for the booking; may or may not be travelling."""

    given_name: str | None = meta("Given name(s) of the booker.", default=None)
    family_name: str | None = meta("Family name of the booker.", default=None)
    full_name: str | None = meta("Full name when the partner does not split it.", default=None)
    email: str | None = meta("Contact email.", default=None)
    phones: list[str] = meta("Contact phone numbers; partners may give several.", default=[])


class ActivityDetails(BaseModel):
    option_id: str | None = meta("Partner's option / variant / rate identifier.", default=None)
    option_name: str | None = meta("Display name of the option.", default=None)
    slot_id: str | None = meta(
        "Partner's identifier of the booked date/time inventory slot.", default=None
    )
    service_language: str | None = meta("Language the activity is delivered in.", default=None)


class CruiseDetails(BaseModel):
    voyage_id: str | None = meta("Partner's sailing / voyage identifier.", default=None)
    fare_category_code: str | None = meta("Priced fare or cabin category code.", default=None)
    cabin_number: str | None = meta("Assigned cabin number, if any.", default=None)
    deck: str | None = meta("Deck name or number of the cabin.", default=None)
    balance_due_date: date | None = meta(
        "Date the remaining balance must be paid.", default=None, critical=True
    )


class Booking(BaseModel):
    our_booking_id: str = meta("padan's own booking ID.", source="ours")
    partner_booking_id: str | None = meta(
        "The partner's system identifier for this booking (used in API calls).",
        default=None,
        critical=True,
    )
    partner_confirmation_code: str | None = meta(
        "The code a customer quotes to the partner, when it differs from partner_booking_id.",
        default=None,
    )
    status: Literal["on_hold", "pending", "confirmed", "cancelled", "failed"] = meta(
        "Booking state. on_hold: reserved, expires unless we confirm; "
        "pending: we confirmed, the partner has not yet.",
        critical=True,
    )
    hold_expires_at: datetime | None = meta(
        "When an on_hold booking expires if not confirmed.", default=None, critical=True
    )
    booked_at: datetime | None = meta("When the partner created the booking.", default=None)
    product_id: str | None = meta("Partner's product (or sailing) identifier.", default=None)
    product_name: str | None = meta("Display name of the product.", default=None)
    start_date: date = meta("Local start date of the experience or sailing.", critical=True)
    start_time: time | None = meta(
        "Local start time, no timezone; None if the partner gives a date only.", default=None
    )
    end_date: date | None = meta("Local end date, if the product spans several days.", default=None)
    end_time: time | None = meta("Local end time, no timezone.", default=None)
    contact: Contact = meta("The person who made and pays for the booking.")
    travellers: list[Traveller] = meta("Everyone travelling; exactly one is the lead.")
    total_price: Money | None = meta(
        "Gross total: what the customer pays at the partner's price.", default=None, critical=True
    )
    net_price: Money | None = meta(
        "Net total: what we owe the partner for this booking.", default=None, critical=True
    )
    cancellable: bool | None = meta(
        "Whether the partner allows this booking to be cancelled now.", default=None
    )
    cancellation_policy: str | None = meta(
        "Cancellation terms as given by the partner.", default=None, critical=True
    )
    fulfilment: list[Fulfilment] = meta(
        "Vouchers and tickets the customer uses to get in.", default=[], critical=True
    )
    custom_fields: list[CustomField] = meta(
        "Partner-specific questions answered for the whole booking.", default=[]
    )
    activity: ActivityDetails | None = None
    cruise: CruiseDetails | None = None

    @model_validator(mode="after")
    def check_invariants(self) -> "Booking":
        lead_travellers = [traveller for traveller in self.travellers if traveller.is_lead]
        if len(lead_travellers) != 1:
            raise ValueError("exactly one traveller must have is_lead == True")
        if (self.activity is None) == (self.cruise is None):
            raise ValueError("exactly one of activity or cruise must be set")
        return self
