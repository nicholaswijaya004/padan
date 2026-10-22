"""decide(): the escalation policy that turns candidates into labels (E2). You write decide()."""

from padan.candidates import Candidate
from padan.engine import Decision, decide


def cand(
    *targets: str, escalate: bool = False, transforms: tuple[str | None, ...] = ()
) -> Candidate:
    return Candidate(tuple(targets), entry="test", escalate=escalate, transforms=transforms)


# --- step 1: nothing matched ---------------------------------------------------------------------


def test_no_candidate_is_none() -> None:
    assert decide([]) == [Decision("NONE")]


# --- step 2: learnt from an ASK_PARTNER label ----------------------------------------------------


def test_an_escalating_candidate_asks_with_its_target() -> None:
    found = [cand("total_price.amount", escalate=True)]
    assert decide(found) == [Decision("ASK_PARTNER", candidate="total_price.amount")]


def test_escalation_wins_over_a_plain_candidate() -> None:
    found = [cand("items[].activity.service_language"), cand("items[].option_id", escalate=True)]
    assert decide(found) == [Decision("ASK_PARTNER", candidate="items[].option_id")]


# --- step 3: two different readings --------------------------------------------------------------


def test_two_readings_with_a_critical_one_ask() -> None:
    found = [cand("total_price.amount"), cand("net_price.amount")]
    assert decide(found) == [Decision("ASK_PARTNER", candidate="net_price.amount")]  # sorted first


def test_two_readings_without_a_critical_one_are_left_blank() -> None:
    found = [cand("items[].product_name"), cand("items[].option_name")]
    assert decide(found) == [Decision("NONE")]


def test_the_same_reading_twice_is_one_reading() -> None:
    found = [cand("contact.email"), cand("contact.email")]
    assert decide(found) == [Decision("contact.email", "direct")]


# --- step 4: one reading -------------------------------------------------------------------------


def test_one_reading_maps_directly() -> None:
    assert decide([cand("booked_at")]) == [Decision("booked_at", "direct")]


def test_a_split_maps_every_target_with_its_transform() -> None:
    found = [
        cand("items[].start_date", "items[].start_time", transforms=("date_part", "time_part"))
    ]
    assert decide(found) == [
        Decision("items[].start_date", "transform", "date_part"),
        Decision("items[].start_time", "transform", "time_part"),
    ]


def test_a_critical_enum_without_a_map_asks() -> None:
    # copying a raw partner code (UNCAPTURED, 42) into status is a silent wrong value
    assert decide([cand("status")]) == [Decision("ASK_PARTNER", candidate="status")]


def test_a_minor_enum_without_a_map_is_still_mapped() -> None:
    found = [cand("travellers[].traveller_type")]
    assert decide(found) == [Decision("travellers[].traveller_type", "direct")]
