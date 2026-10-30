"""Test labels from the canonical side: the sheet, the NONE fill and the freeze."""

from pathlib import Path

import pytest
import yaml

from padan.baselines import gold_files
from padan.extract import ExtractedField
from padan.labels import LABELS, VALID_TARGETS
from padan.sheet import ROWS, Row, fill, freeze, main, render_sheet, verify

BOOK, GET = "POST /book", "GET /book/{id}"
FIELDS = [
    ExtractedField(endpoint=BOOK, direction="request", path=p, type="string", evidence=f"{p} doc.")
    for p in ["email", "first", "last", "answers[].value"]
] + [ExtractedField(endpoint=GET, direction="response", path="total", type="number", evidence="T.")]


def rows(text: str) -> list[Row]:
    return ROWS.validate_python(yaml.safe_load(text))


SHEET = """
- target: 'contact.email'
  picks:
    - source: {endpoint: 'POST /book', direction: request, paths: ['email']}
      kind: direct
- target: 'travellers[].full_name'
  picks:
    - source: {endpoint: 'POST /book', direction: request, paths: ['first', 'last']}
      kind: derived
      transform: 'concat(first, last)'
- target: 'contact.phones[]'
  picks:
    - source: {endpoint: 'POST /book', direction: request, paths: ['answers[id=PHONE].value']}
      kind: transform
      transform: 'to_e164'
- target: 'total_price.amount'
  picks:
    - source: {endpoint: 'GET /book/{id}', direction: response, paths: ['total']}
      kind: ask
      question: 'Is total the gross amount?'
- target: 'status'
  picks: []
"""


def test_the_sheet_has_every_target_once_with_no_picks() -> None:
    parsed = rows(render_sheet("demo"))
    assert [row.target for row in parsed] == sorted(VALID_TARGETS)
    assert all(row.picks == [] for row in parsed)
    assert "# [critical]" in render_sheet("demo")


def test_fill_places_picks_and_sets_every_other_field_to_none() -> None:
    entries = fill(rows(SHEET), FIELDS)
    assert [(e["source"]["paths"], e["target"]) for e in entries] == [
        (["email"], "contact.email"),
        (["first", "last"], "travellers[].full_name"),  # once, at its first field; `last` covered
        (["answers[id=PHONE].value"], "contact.phones[]"),  # the filter is kept
        (["total"], "ASK_PARTNER"),
    ]
    assert entries[3]["candidate"] == "total_price.amount"
    assert entries[0]["evidence"] == "email doc."
    LABELS.validate_python(entries)  # the same format as every dev label file


def test_a_pick_can_narrow_its_target_with_a_filter() -> None:
    sheet = """
- target: 'fulfilment[].value'
  picks:
    - source: {endpoint: 'GET /book/{id}', direction: response, paths: ['total']}
      kind: ask
      target: 'fulfilment[kind=voucher].value'
      question: 'Is this the voucher link?'
- target: 'fulfilment[].kind'
  picks: []
"""
    (entry,) = [e for e in fill(rows(sheet), FIELDS) if e["target"] != "NONE"]
    assert entry["candidate"] == "fulfilment[kind=voucher].value"
    LABELS.validate_python([entry])


def test_a_narrowed_target_must_be_a_form_of_its_row() -> None:
    wrong = "- target: 'fulfilment[].value'\n  picks:\n    - source: {endpoint: 'POST /book', "
    wrong += "direction: request, paths: ['email']}\n      kind: direct\n"
    wrong += "      target: 'fulfilment[kind=voucher].format'\n"
    with pytest.raises(ValueError, match="is not a form of"):
        rows(wrong)


def test_an_unpicked_field_is_none() -> None:
    entries = fill(rows("- target: 'status'\n  picks: []\n"), FIELDS)
    assert [e["target"] for e in entries] == ["NONE"] * len(FIELDS)
    assert entries[0] == {
        "source": {"endpoint": BOOK, "direction": "request", "paths": ["email"]},
        "target": "NONE",
        "evidence": "email doc.",
    }


def test_a_pick_must_name_a_scoped_field() -> None:
    typo = "- target: 'contact.email'\n  picks:\n    - source: {endpoint: 'POST /book', "
    typo += "direction: request, paths: ['emial']}\n      kind: direct\n"
    with pytest.raises(ValueError, match="emial is not a scoped field"):
        fill(rows(typo), FIELDS)


def test_a_row_must_be_a_schema_target() -> None:
    with pytest.raises(ValueError, match="not a Booking schema path"):
        rows("- target: 'contact.mail'\n  picks: []\n")


def test_freeze_adds_new_files_and_refuses_a_changed_one(tmp_path: Path) -> None:
    (tmp_path / "sheets").mkdir()
    (tmp_path / "a.yaml").write_text("a\n")
    (tmp_path / "sheets" / "a.yaml").write_text("s\n")
    recorded = freeze(tmp_path, {})
    assert set(recorded) == {"a.yaml", "sheets/a.yaml"}
    (tmp_path / "b.yaml").write_text("b\n")
    assert set(freeze(tmp_path, recorded)) == {"a.yaml", "b.yaml", "sheets/a.yaml"}
    (tmp_path / "a.yaml").write_text("a, edited\n")
    with pytest.raises(ValueError, match=r"a\.yaml changed after it was frozen"):
        freeze(tmp_path, recorded)


def test_verify_reports_changed_and_missing_files(tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("a\n")
    (tmp_path / "b.yaml").write_text("b\n")
    recorded = freeze(tmp_path, {})
    assert verify(tmp_path, recorded) == []
    (tmp_path / "a.yaml").write_text("a, edited\n")
    (tmp_path / "b.yaml").unlink()
    assert verify(tmp_path, recorded) == ["changed  a.yaml", "missing  b.yaml"]


def test_new_never_overwrites_a_sheet(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["new", "demo"]) == 0
    sheet = tmp_path / "data/labels/test/sheets/demo.yaml"
    sheet.write_text("my labels\n")
    assert main(["new", "demo"]) == 1
    assert sheet.read_text() == "my labels\n"


def test_dev_tooling_never_reads_test_labels(tmp_path: Path) -> None:
    (tmp_path / "test").mkdir()
    (tmp_path / "dev.yaml").write_text("[]\n")
    (tmp_path / "test" / "viator-partner.yaml").write_text("[]\n")
    assert gold_files(tmp_path) == [tmp_path / "dev.yaml"]
