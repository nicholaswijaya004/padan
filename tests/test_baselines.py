"""Baselines and the report: prediction files are valid label files, and the floor is a floor."""

from pathlib import Path

import pytest

from padan.baselines import all_none, dump, fields_of, gold_files, leaf, name_match
from padan.labels import LabelEntry, load_labels
from padan.report import macro, score_dir, table
from padan.score import score_spec

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD = gold_files(REPO_ROOT / "data" / "labels")

EP, DIR = "GET /bookings/{id}", "response"


def field(path: str) -> tuple[str, str, str, str]:
    return (EP, DIR, path, "-")


def test_leaf_takes_the_last_name_without_case_or_underscores() -> None:
    assert leaf("ReservationInfo.ReservationID@BookedDate") == "bookeddate"
    assert leaf("travellers[].given_name") == "givenname"
    assert leaf("unitItems[].status") == "status"


def test_fields_drop_filters_and_appear_once() -> None:
    gold = [
        LabelEntry.model_validate(
            {
                "source": {"endpoint": EP, "direction": DIR, "paths": [path]},
                "target": "NONE",
                "evidence": "-",
            }
        )
        for path in ["inputFields[id=EMAIL].value", "inputFields[id=PHONE].value", "status"]
    ]
    assert [f[2] for f in fields_of(gold)] == ["inputFields[].value", "status"]


def test_name_match_maps_one_match_and_nothing_else() -> None:
    predicted = name_match([field("status"), field("price.currency"), field("uuid")])
    assert [p.target for p in predicted] == ["status", "NONE", "NONE"]  # currency: 2 matches
    assert predicted[0].kind == "direct"


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.stem)
def test_all_none_is_the_floor(path: Path) -> None:
    gold = load_labels(path)
    score = score_spec(gold, all_none(fields_of(gold)))
    assert score.mapping.tp == score.mapping.fp == 0
    assert score.critical_errors == []
    assert score.escalation.fn == sum(e.target == "ASK_PARTNER" for e in gold)


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.stem)
def test_prediction_files_load_as_label_files(path: Path, tmp_path: Path) -> None:
    predicted = name_match(fields_of(load_labels(path)))
    (tmp_path / path.name).write_text(dump(predicted))
    assert load_labels(tmp_path / path.name) == predicted


def test_report_scores_gold_against_itself_and_a_missing_file_as_none(tmp_path: Path) -> None:
    labels, pred = tmp_path / "labels", tmp_path / "pred"
    labels.mkdir()
    pred.mkdir()
    for name in ["a.yaml", "b.yaml"]:
        (labels / name).write_text(GOLD[0].read_text())
    (pred / "a.yaml").write_text(GOLD[0].read_text())
    scores = score_dir(pred, labels)
    assert scores["a"].mapping.f1 == 1.0
    assert scores["b"].mapping.tp == 0  # no prediction file
    assert "| **macro (headline)** |" in table(scores)


def test_macro_skips_undefined_values() -> None:
    assert macro([1.0, None, 0.5]) == 0.75
    assert macro([None]) is None
