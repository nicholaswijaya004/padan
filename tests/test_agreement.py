"""The second-labeller check: a seeded stratified sample, and agreement with the gold."""

from pathlib import Path

import pytest

from padan.agreement import draw, kappa, score, stratum, their_targets

GOLD = {
    ("POST /b", "request", f"f{i}"): t
    for i, t in enumerate(["NONE"] * 6 + ["ASK_PARTNER"] + ["contact.email", "status"])
}


def test_stratum() -> None:
    assert [stratum(t) for t in ["NONE", "ASK_PARTNER", "status"]] == ["none", "ask", "mapped"]


def test_draw_is_seeded_and_stratified() -> None:
    sizes = {"mapped": 1, "ask": 1, "none": 2}
    first = draw(GOLD, sizes, seed=7)
    assert first == draw(GOLD, sizes, seed=7)
    assert sorted(stratum(GOLD[k]) for k in first) == ["ask", "mapped", "none", "none"]


def test_kappa_known_values() -> None:
    assert kappa([("a", "a"), ("b", "b")]) == 1.0
    # observed 0.5; each labeller says a half the time, so chance is 0.5 and kappa is 0
    assert kappa([("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]) == 0.0
    assert kappa([("a", "a"), ("a", "a")]) is None


def test_score_counts_agreement_per_stratum() -> None:
    sample = list(GOLD)
    theirs = dict(GOLD) | {("POST /b", "request", "f0"): "contact.email"}
    report = score(GOLD, sample, theirs)
    assert (report["fields"], report["agree"]) == (9, 8)
    assert report["by_stratum"] == {"mapped": "2/2", "ask": "1/1", "none": "5/6"}
    assert report["disagreements"] == [{"path": "f0", "gold": "NONE", "theirs": "contact.email"}]


def test_score_refuses_an_unlabelled_field() -> None:
    with pytest.raises(ValueError, match="no target"):
        score(GOLD, list(GOLD), {})


def test_their_targets_read_filters_as_lists(tmp_path: Path) -> None:
    sheet = tmp_path / "s.yaml"
    sheet.write_text(
        "- source: {endpoint: 'POST /b', direction: request, paths: ['a[0].b']}\n"
        "  target: 'fulfilment[kind=voucher].value'\n"
    )
    assert their_targets(sheet) == {("POST /b", "request", "a[].b"): "fulfilment[].value"}
