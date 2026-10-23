"""The rule engine end to end: fields -> predictions + receipts, and the variants it writes."""

from pathlib import Path
from typing import Any

import pytest

from padan.candidates import Lexicon
from padan.engine import ENUMS, main, predict
from padan.labels import load_labels

EP = "GET /bookings/{id}"
LEX = Lexicon.model_validate(
    {
        "entities": {"contact": ["contact"]},
        "wrappers": [],
        "dependents": ["contact"],
        "entries": [
            {
                "id": "id",
                "targets": ["partner_booking_id"],
                "leaf": [["id"]],
                "context": [""],
                "learnt_from": ["octo"],
            },
            {
                "id": "email",
                "targets": ["contact.email"],
                "leaf": [["email"]],
                "context": ["contact"],
                "learnt_from": ["general"],
            },
            {
                "id": "status",
                "targets": ["status"],
                "leaf": [["status"]],
                "context": [""],
                "learnt_from": ["octo", "headout"],
            },
        ],
    }
)


def fields(*paths: str) -> list[Any]:
    return [(EP, "response", path, "-") for path in paths]


def test_enum_targets_come_from_the_schema() -> None:
    assert {
        "status",
        "travellers[].traveller_type",
        "fulfilment[].kind",
        "fulfilment[].format",
    } == ENUMS


def test_predict_maps_asks_and_leaves_blank_with_a_receipt_per_field() -> None:
    entries, receipts = predict(fields("id", "contact.email", "status", "uuid"), LEX, off=[])
    assert [e.target for e in entries] == [
        "partner_booking_id",
        "contact.email",
        "ASK_PARTNER",
        "NONE",
    ]
    assert entries[2].candidate == "status" and entries[2].question
    assert [r["entries"] for r in receipts] == [["id"], ["email"], ["status"], []]


def test_r4_maps_a_documented_enum_and_still_asks_about_status() -> None:
    lex = LEX.model_copy(
        update={
            "entries": [
                *LEX.entries,
                LEX.entries[0].model_copy(
                    update={
                        "id": "format",
                        "targets": ["fulfilment[kind=voucher].format"],
                        "leaf": [["format"]],
                    }
                ),
            ]
        }
    )
    documented = [
        (EP, "response", "format", "possible values are: `QRCODE` or `PDF_URL`."),
        (EP, "response", "status", "One of `PENDING`, `CONFIRMED`, `CANCELLED`."),
    ]
    entries, _ = predict(documented, lex, off=[])
    assert [(e.target, e.transform) for e in entries] == [
        ("fulfilment[kind=voucher].format", "enum_map(QRCODE=qrcode, PDF_URL=pdf_url)"),
        ("ASK_PARTNER", None),  # a lifecycle enum: name matches can be false friends
    ]


def test_off_switches_off_a_spec_and_the_general_synonyms() -> None:
    entries, _ = predict(fields("id", "contact.email"), LEX, off=["octo", "general"])
    assert [e.target for e in entries] == ["NONE", "NONE"]


def test_main_writes_both_variants_as_valid_label_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    assert main([str(tmp_path)]) == 0
    for variant in ("rules_strict", "rules_general"):
        files = sorted((tmp_path / variant).glob("*.yaml"))
        assert [f.stem for f in files] == [
            "headout-partner",
            "hotelbeds-activities",
            "hx-swota",
            "octo-core",
        ]
        for f in files:
            load_labels(f)  # raises if a prediction is not a valid label
            assert (tmp_path / variant / f"{f.stem}.rules.json").exists()
