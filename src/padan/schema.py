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


class Traveller(BaseModel):
    given_name: str | None = meta("Given name(s) as on the travel document.", default=None)
    family_name: str | None = meta("Family name; None for single-name travellers.", default=None)
    full_name: str | None = meta(
        "Full name when the partner does not split it (e.g. Headout NAME).", default=None
    )
    traveller_type: Literal["adult", "child", "infant", "senior"] | None = meta(
        "Pricing category of this traveller.", default=None
    )
    age: int | None = meta("Age in years at time of travel.", default=None)
    is_lead: bool = meta("True for the lead traveller of the booking.")

    @model_validator(mode="after")
    def has_a_name(self) -> "Traveller":
        if not self.given_name and not self.full_name:
            raise ValueError("traveller needs given_name or full_name")
        return self


class Contact(BaseModel):
    name: str | None = meta("Name of the person who made the booking.", default=None)
    email: str | None = meta("Contact email.", default=None)
    phones: list[str] = meta("Contact phone numbers; partners may give several.", default=[])


class ActivityDetails(BaseModel):
    option_id: str | None = meta("Partner's option / variant / rate identifier.", default=None)
    option_name: str | None = meta("Display name of the option.", default=None)
    voucher_url: str | None = meta("URL of the voucher or ticket.", default=None)
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
        "The partner's reference for this booking.", default=None, critical=True
    )
    status: Literal["pending", "confirmed", "cancelled", "failed"] = meta(
        "Booking state, normalised from the partner's own status values.", critical=True
    )
    booked_at: datetime | None = meta("When the partner created the booking.", default=None)
    product_id: str | None = meta("Partner's product (or sailing) identifier.", default=None)
    product_name: str | None = meta("Display name of the product.", default=None)
    start_date: date = meta("Local start date of the experience or sailing.", critical=True)
    start_time: time | None = meta(
        "Local start time, no timezone; None if the partner gives a date only.", default=None
    )
    end_date: date | None = meta("Local end date, if the product spans several days.", default=None)
    contact: Contact = meta("The person who made and pays for the booking.")
    travellers: list[Traveller] = meta("Everyone travelling; exactly one is the lead.")
    total_price: Money | None = meta(
        "Total the customer pays for this booking.", default=None, critical=True
    )
    cancellation_policy: str | None = meta(
        "Cancellation terms as given by the partner.", default=None, critical=True
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
