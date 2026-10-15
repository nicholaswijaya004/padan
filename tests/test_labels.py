from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from padan.labels import VALID_TARGETS, LabelEntry, load_labels, normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
LABEL_DIR = REPO_ROOT / "data" / "labels"
GOLD_FILES = sorted(p for p in LABEL_DIR.glob("*.yaml") if p.name != "dry_run.yaml")


def label(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "source": {"endpoint": "GET /bookings/{id}", "direction": "response", "paths": ["id"]},
        "target": "partner_booking_id",
        "kind": "direct",
        "evidence": "The booking ID.",
    }
    return entry | overrides


# --- target paths ------------------------------------------------------------------------------


def test_normalise_drops_filters_and_positions() -> None:
    assert normalise("travellers[is_lead=true].contact[0].email") == "travellers[].contact[].email"


def test_target_paths_cover_leaves_nested_and_lists() -> None:
    assert {
        "partner_booking_id",
        "our_booking_id",
        "total_price.amount",
        "contact.phones[]",
        "travellers[]",
        "travellers[].custom_fields[].field_id",
        "activity.slot_id",
        "cruise.balance_due_date",
    } <= VALID_TARGETS


def test_target_paths_exclude_containers() -> None:
    assert "total_price" not in VALID_TARGETS
    assert "activity" not in VALID_TARGETS


# --- one entry ---------------------------------------------------------------------------------


def test_valid_direct_label() -> None:
    LabelEntry.model_validate(label())


def test_filter_in_target_is_accepted() -> None:
    LabelEntry.model_validate(label(target="travellers[is_lead=true].full_name"))


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"target": "partner_product_id"}, id="invented-target"),
        pytest.param({"target": "product_id, activity.option_id"}, id="two-targets"),
        pytest.param({"target": "ASK PARTNER", "kind": None}, id="ask-partner-with-space"),
        pytest.param({"kind": None}, id="canonical-without-kind"),
        pytest.param({"target": "NONE"}, id="none-with-kind"),
        pytest.param({"kind": "transform"}, id="transform-without-function"),
        pytest.param({"transform": "upper()"}, id="direct-with-function"),
        pytest.param({"evidence": ""}, id="no-evidence"),
        pytest.param({"question": "Why?"}, id="question-without-ask-partner"),
    ],
)
def test_invalid_labels_are_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        LabelEntry.model_validate(label(**overrides))


def test_scaffold_empty_kind_counts_as_missing() -> None:
    entry = LabelEntry.model_validate(label(target="NONE", kind=""))
    assert entry.kind is None


def test_ask_partner_needs_question_and_real_candidate() -> None:
    ask = label(target="ASK_PARTNER", kind=None, candidate="total_price.amount")
    with pytest.raises(ValidationError):
        LabelEntry.model_validate(ask)
    LabelEntry.model_validate(ask | {"question": "Is this the total or per person?"})
    with pytest.raises(ValidationError):
        LabelEntry.model_validate(ask | {"question": "?", "candidate": "partner_item_id"})


# --- files -------------------------------------------------------------------------------------


def test_duplicate_source_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    path.write_text(yaml.safe_dump([label(), label()]))
    with pytest.raises(ValueError, match="labelled twice"):
        load_labels(path)


def test_one_source_may_feed_two_targets(tmp_path: Path) -> None:
    path = tmp_path / "x.yaml"
    split = {"kind": "transform", "transform": "date_part"}
    path.write_text(
        yaml.safe_dump([label(target="start_date", **split), label(target="start_time", **split)])
    )
    assert len(load_labels(path)) == 2


@pytest.mark.parametrize("path", GOLD_FILES, ids=lambda p: p.name)
def test_gold_label_file_is_valid(path: Path) -> None:
    load_labels(path)


@pytest.mark.parametrize("path", GOLD_FILES, ids=lambda p: p.name)
def test_gold_label_file_is_named_after_a_manifest_id(path: Path) -> None:
    manifest = yaml.safe_load((REPO_ROOT / "data" / "manifest.yaml").read_text())
    assert path.stem in {entry["id"] for entry in manifest}
