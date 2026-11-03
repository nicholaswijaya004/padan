"""What padan adds to a generated client's record before it is a Booking (M3, Day 23).

A partner's response cannot hold what only padan knows: padan's own booking ID, the vertical it
sells (an activity or a cruise), and, when the partner does not flag one, which traveller is the
lead. The rule for the lead (decided on Day 23): the traveller whose name matches the booking
contact, else the first traveller. Every choice is returned as a note: nothing is filled silently.
"""

import copy
from typing import Any, Literal

from padan.schema import Booking

Record = dict[str, Any]


def full_name(person: Record) -> str:
    """A person's name for matching: full_name, else given + family; compared case-insensitively."""
    name = person.get("full_name") or " ".join(
        part for part in (person.get("given_name"), person.get("family_name")) if part
    )
    return " ".join(str(name).split()).casefold()


def choose_lead(record: Record) -> str:
    """Mark exactly one lead traveller (rule B) and say how it was chosen."""
    travellers: list[Record] = record.get("travellers") or []
    if not travellers:
        return "lead: no travellers in the record"
    if any(t.get("is_lead") is True for t in travellers):
        for traveller in travellers:
            traveller.setdefault("is_lead", False)
        return "lead: given by the partner"
    contact = full_name(record.get("contact") or {})
    match = next((t for t in travellers if contact and full_name(t) == contact), None)
    lead = match or travellers[0]
    for traveller in travellers:
        traveller["is_lead"] = traveller is lead
    return "lead: the traveller matching the contact" if match else "lead: the first traveller"


def to_booking(
    record: Record, our_booking_id: str, vertical: Literal["activity", "cruise"] = "activity"
) -> tuple[Booking, list[str]]:
    """A client's record plus padan's own fields, validated as a Booking; with notes on each choice.
    Raises pydantic.ValidationError when something only the partner could give is still missing."""
    record = copy.deepcopy(record)
    notes = []
    echoed = record.get("our_booking_id")
    if echoed not in (None, our_booking_id):
        notes.append(f"our_booking_id: the partner echoes {echoed!r}; padan's own ID is used")
    record["our_booking_id"] = our_booking_id
    for item in record.get("items") or []:
        if item.get("activity") is None and item.get("cruise") is None:
            item[vertical] = {}
            notes.append(f"item: vertical set to {vertical}")
    notes.append(choose_lead(record))
    return Booking.model_validate(record), notes
