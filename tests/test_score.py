"""The scorer on small hand-made label sets, then every gold file scored against itself."""

from pathlib import Path
from typing import Any

import pytest

from padan.labels import LabelEntry, load_labels
from padan.score import CRITICAL, Counts, Pair, score_spec

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_FILES = sorted(
    p for p in (REPO_ROOT / "data" / "labels").glob("*.yaml") if p.name != "dry_run.yaml"
)

EP = "GET /bookings/{id}"


def lab(path: str, target: str, kind: str | None = "direct", **extra: Any) -> LabelEntry:
    if target in ("NONE", "ASK_PARTNER"):
        kind = None
    if target == "ASK_PARTNER":
        extra.setdefault("question", "Which one?")
    return LabelEntry.model_validate(
        {
            "source": {"endpoint": EP, "direction": "response", "paths": [path]},
            "target": target,
            "kind": kind,
            "evidence": "-",
            **extra,
        }
    )


def pair(path: str, target: str) -> Pair:
    return Pair(EP, "response", path, target)


# --- the helpers given to you ------------------------------------------------------------------


def test_counts_are_none_when_undefined() -> None:
    empty = Counts()
    assert (empty.precision, empty.recall, empty.f1) == (None, None, None)
    assert Counts(tp=0, fp=0, fn=3).recall == 0.0
    assert Counts(tp=0, fp=0, fn=3).f1 == 0.0
    assert Counts(tp=3, fp=1, fn=0).f1 == pytest.approx(6 / 7)


def test_critical_targets_include_fields_inside_a_critical_field() -> None:
    assert {
        "total_price.amount",
        "total_price.currency",
        "fulfilment[].value",
        "items[].start_date",
    } <= (CRITICAL)
    assert "items[].product_name" not in CRITICAL
    assert "travellers[].given_name" not in CRITICAL


# --- 1. mapping --------------------------------------------------------------------------------


def test_identical_labels_score_perfectly() -> None:
    gold = [lab("id", "partner_booking_id"), lab("ref", "NONE")]
    score = score_spec(gold, gold)
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (1, 0, 0)
    assert score.mapping.f1 == 1.0
    assert score.errors == [] and score.critical_errors == []


def test_a_missing_prediction_is_none_so_a_miss() -> None:
    score = score_spec([lab("id", "partner_booking_id")], [])
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (0, 0, 1)
    assert score.errors == [("FN", pair("id", "partner_booking_id"))]


def test_mapping_a_gold_none_field_is_a_false_positive() -> None:
    score = score_spec([lab("name", "NONE")], [lab("name", "items[].product_name")])
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (0, 1, 0)
    assert score.critical_errors == []  # items[].product_name is not critical


def test_a_wrong_target_is_one_fp_and_one_fn() -> None:
    score = score_spec([lab("name", "items[].product_name")], [lab("name", "items[].option_name")])
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (0, 1, 1)


def test_first_item_and_any_item_are_the_same_path() -> None:
    gold = [lab("activities[0].code", "items[].product_id")]
    pred = [lab("activities[].code", "items[].product_id")]
    assert score_spec(gold, pred).mapping.tp == 1


def test_filters_must_match() -> None:
    gold = [lab("inputFields[id=EMAIL].value", "contact.email")]
    pred = [lab("inputFields[id=PHONE].value", "contact.email")]
    score = score_spec(gold, pred)
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (0, 1, 1)


def test_one_field_with_two_targets_is_two_pairs() -> None:
    gold = [
        lab("startDateTime", "items[].start_date", "transform", transform="date_part"),
        lab("startDateTime", "items[].start_time", "transform", transform="time_part"),
    ]
    pred = gold[:1]
    score = score_spec(gold, pred)
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (1, 0, 1)


# --- 2. escalation -----------------------------------------------------------------------------


def test_asking_when_gold_asks_is_an_escalation_hit_not_a_mapping() -> None:
    gold = [lab("price", "ASK_PARTNER", candidate="total_price.amount")]
    score = score_spec(gold, gold)
    assert (score.escalation.tp, score.escalation.fp, score.escalation.fn) == (1, 0, 0)
    assert (score.mapping.tp, score.mapping.fp, score.mapping.fn) == (0, 0, 0)


def test_guessing_the_candidate_is_wrong_and_critical_s1() -> None:
    gold = [lab("price", "ASK_PARTNER", candidate="total_price.amount")]
    pred = [lab("price", "total_price.amount")]
    score = score_spec(gold, pred)
    assert (score.mapping.fp, score.escalation.fn) == (1, 1)
    assert score.critical_errors == [pair("price", "total_price.amount")]


def test_asking_when_gold_maps_costs_a_question_not_a_critical_error_s2() -> None:
    gold = [lab("price", "total_price.amount")]
    pred = [lab("price", "ASK_PARTNER", candidate="total_price.amount")]
    score = score_spec(gold, pred)
    assert (score.mapping.fn, score.escalation.fp) == (1, 1)
    assert score.critical_errors == []


# --- 3. transforms -----------------------------------------------------------------------------


def test_an_enum_map_in_another_order_is_the_same_transform() -> None:
    gold = [
        lab(
            "type",
            "travellers[].traveller_type",
            "transform",
            transform="enum_map(A=adult, C=child)",
        )
    ]
    pred = [
        lab(
            "type",
            "travellers[].traveller_type",
            "transform",
            transform="enum_map(C=child, A=adult)",
        )
    ]
    score = score_spec(gold, pred)
    assert (score.transforms_right, score.transforms_total) == (1, 1)


def test_a_wrong_transform_on_a_critical_target_is_a_critical_error() -> None:
    gold = [lab("startDateTime", "items[].start_date", "transform", transform="date_part")]
    pred = [lab("startDateTime", "items[].start_date", "direct")]
    score = score_spec(gold, pred)
    assert score.mapping.tp == 1  # the target is right...
    assert (score.transforms_right, score.transforms_total) == (0, 1)  # ...the value is not
    assert score.errors == [("TRANSFORM", pair("startDateTime", "items[].start_date"))]
    assert score.critical_errors == [pair("startDateTime", "items[].start_date")]


def test_direct_on_both_sides_is_not_a_transform() -> None:
    gold = [lab("id", "partner_booking_id")]
    assert score_spec(gold, gold).transforms_total == 0


def test_derived_recipes_are_scored_on_the_target_only() -> None:
    gold = [lab("count", "travellers[]", "derived", transform="count of customers")]
    pred = [lab("count", "travellers[]", "derived", transform="len(customers)")]
    score = score_spec(gold, pred)
    assert (score.mapping.tp, score.transforms_total) == (1, 0)


# --- every gold file against itself --------------------------------------------------------------


@pytest.mark.parametrize("path", GOLD_FILES, ids=lambda p: p.stem)
def test_gold_scored_against_itself_is_perfect(path: Path) -> None:
    gold = load_labels(path)
    score = score_spec(gold, gold)
    assert score.mapping.fp == score.mapping.fn == 0
    assert score.escalation.fp == score.escalation.fn == 0
    assert score.transforms_right == score.transforms_total
    assert score.errors == [] and score.critical_errors == []
