"""Candidate finder: leaf words, entity context, specificity, and leave-one-spec-out."""

from typing import Any

import pytest
from pydantic import ValidationError

from padan.candidates import (
    Entry,
    Lexicon,
    candidates,
    context_key,
    entity_path,
    load_lexicon,
    split,
)

HEAD: dict[str, Any] = {
    "entities": {
        "traveller": ["customers", "paxes", "guest"],
        "contact": ["contact", "holder"],
        "ticket": ["unit", "ticket"],
        "cabin": ["cabin"],
        "item": ["activities", "sailing"],
        "booking": ["reservation"],
    },
    "wrappers": ["info", "details", "selected", "person", "name"],
    "dependents": ["contact"],
}


def entry(target: str, leaf: list[str], context: list[str], spec: str = "a") -> dict[str, Any]:
    return {
        "id": target,
        "targets": [target],
        "leaf": [leaf],
        "context": context,
        "learnt_from": [spec],
    }


def lexicon(*entries: dict[str, Any]) -> Lexicon:
    return Lexicon.model_validate(HEAD | {"entries": list(entries)})


LEX = lexicon(
    entry("partner_booking_id", ["id"], [""]),
    entry("status", ["status"], [""]),
    entry("contact.given_name", ["first", "name"], ["contact"]),
    entry("travellers[].given_name", ["first", "name"], ["ticket contact", "traveller"], spec="b"),
)


# --- split and context -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "leaf", "parents"),
    [
        ("id", "id", []),
        ("unitItems[].contact.firstName", "firstName", ["unitItems", "contact"]),
        ("ReservationID@BookedDate", "BookedDate", ["ReservationID"]),
        ("inputFields[id=EMAIL].value", "value", ["inputFields"]),
    ],
)
def test_split_into_leaf_and_parents(path: str, leaf: str, parents: list[str]) -> None:
    assert split(path) == (leaf, parents)


def test_entity_path_skips_wrappers_merges_repeats_and_marks_unknown_objects() -> None:
    parents = ["ReservationInfo", "GuestDetails", "GuestDetail", "ContactInfo", "PersonName"]
    assert entity_path(parents, LEX) == ("booking", "traveller", "contact")
    assert entity_path(["availability"], LEX) == ("other",)


def test_a_dependent_entity_is_read_with_its_owner() -> None:
    assert context_key(("ticket", "contact"), LEX) == "ticket contact"
    assert context_key(("contact",), LEX) == "contact"
    assert context_key((), LEX) == ""
    assert context_key(("booking", "contact"), LEX) == "contact"  # the booking is the root


# --- matching ----------------------------------------------------------------------------------


def targets(path: str, lex: Lexicon = LEX, held_out: str | None = None) -> list[str]:
    off = [held_out] if held_out else []
    return [t for c in candidates(path, lex, off) for t in c.targets]


def test_leaf_words_must_match_exactly() -> None:
    assert targets("status") == ["status"]
    assert targets("statusCode") == []  # {status, code} is not {status}: no "contains" match


def test_context_rules_out_a_ticket_or_cabin_status() -> None:
    assert targets("unitItems[].status") == []
    assert targets("SailingInfo.SelectedCabin@Status") == []


def test_booking_id_only_at_the_root_or_under_a_reservation() -> None:
    assert targets("id") == ["partner_booking_id"]
    assert targets("ReservationID@ID") == ["partner_booking_id"]
    assert targets("availability.id") == []  # an unknown object is not the booking


def test_a_ticket_contact_is_not_the_booking_contact() -> None:
    assert targets("contact.firstName") == ["contact.given_name"]
    assert targets("unitItems[].contact.firstName") == ["travellers[].given_name"]


def test_leave_one_spec_out_switches_off_a_specs_own_entries() -> None:
    # no fallback: with the ticket-contact entry off, the booking contact's entry must not match
    assert targets("unitItems[].contact.firstName", held_out="b") == []
    assert targets("unitItems[].contact.firstName", held_out="a") == ["travellers[].given_name"]


def test_general_entries_can_be_switched_off_for_the_strict_score() -> None:
    general = lexicon(entry("status", ["state"], [""], spec="general"))
    assert [c.targets for c in candidates("state", general, off=["octo"])] == [("status",)]
    assert candidates("state", general, off=["octo", "general"]) == []


def test_a_split_entry_carries_one_transform_per_target() -> None:
    split_entry = entry("items[].start_date", ["start", "date", "time"], [""]) | {
        "targets": ["items[].start_date", "items[].start_time"],
        "transforms": ["date_part", "time_part"],
    }
    [found] = candidates("startDateTime", lexicon(split_entry))
    assert found.transforms == ("date_part", "time_part")
    with pytest.raises(ValidationError):
        Entry.model_validate(split_entry | {"transforms": ["date_part"]})


def test_an_entry_learnt_from_two_specs_survives_holding_one_out() -> None:
    shared = lexicon(entry("status", ["status"], [""]) | {"learnt_from": ["a", "b"]})
    assert targets("status", shared, held_out="a") == ["status"]


# --- the lexicon file --------------------------------------------------------------------------


def test_entry_target_must_exist_in_the_schema() -> None:
    with pytest.raises(ValidationError):
        Entry.model_validate(entry("cruise.voyage_id", ["voyage", "id"], ["item"]))


def test_entry_leaf_must_be_words_not_a_partner_path() -> None:
    with pytest.raises(ValidationError):
        Entry.model_validate(entry("status", ["unitItems[].status"], [""]))


def test_the_lexicon_file_loads() -> None:
    lex = load_lexicon()
    assert len(lex.entries) > 0
    assert len({e.id for e in lex.entries}) == len(lex.entries)
