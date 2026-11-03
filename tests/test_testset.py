"""The test-set gate: no test label is read unless all are frozen; systems see extraction only."""

import json
from pathlib import Path

import pytest

from padan import hybrid, testset
from padan.extract import ExtractedField
from padan.llm import PROMPT_VERSION
from padan.sheet import freeze
from padan.testset import sealed_gold, split_test_flag, system_fields


def seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, names: list[str]) -> Path:
    """A sealed test folder under tmp_path, with the gate pointed at it."""
    test_dir = tmp_path / "test"
    (test_dir / "sheets").mkdir(parents=True)
    for name in names:
        (test_dir / name).write_text(f"{name}\n")
        (test_dir / "sheets" / name).write_text("sheet\n")
    frozen = test_dir / "frozen.json"
    frozen.write_text(json.dumps(freeze(test_dir, {})))
    monkeypatch.setattr(testset, "TEST_DIR", test_dir)
    monkeypatch.setattr(testset, "FROZEN", frozen)
    return test_dir


def test_split_test_flag() -> None:
    assert split_test_flag(["out", "--test"]) == (True, ["out"])
    assert split_test_flag(["out"]) == (False, ["out"])


def test_sealed_gold_returns_the_label_files_not_the_sheets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_dir = seal(tmp_path, monkeypatch, ["a.yaml", "b.yaml"])
    assert sealed_gold() == [test_dir / "a.yaml", test_dir / "b.yaml"]


def test_sealed_gold_stops_on_a_changed_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_dir = seal(tmp_path, monkeypatch, ["a.yaml"])
    (test_dir / "sheets" / "a.yaml").write_text("edited\n")
    with pytest.raises(SystemExit, match=r"changed  sheets/a\.yaml"):
        sealed_gold()


def test_sealed_gold_stops_on_a_file_that_was_never_frozen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    test_dir = seal(tmp_path, monkeypatch, ["a.yaml"])
    (test_dir / "b.yaml").write_text("new\n")
    with pytest.raises(SystemExit, match=r"not frozen  b\.yaml"):
        sealed_gold()


def test_sealed_gold_stops_without_a_freeze(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(testset, "TEST_DIR", tmp_path)
    monkeypatch.setattr(testset, "FROZEN", tmp_path / "frozen.json")
    with pytest.raises(SystemExit, match="no label files"):
        sealed_gold()


def test_system_fields_come_from_extraction(monkeypatch: pytest.MonkeyPatch) -> None:
    field = ExtractedField(
        endpoint="POST /x", direction="request", path="a", type="string", evidence="A."
    )
    monkeypatch.setattr(testset, "load_scoped", lambda spec_id: spec_id)
    monkeypatch.setattr(testset, "scoped_fields", lambda entry: [field] if entry == "demo" else [])
    assert system_fields("demo") == [("POST /x", "request", "a", "A.")]


@pytest.mark.parametrize(
    "args",
    [
        ["claude-sonnet-5-5", "general"],
        ["claude-opus-5-5", "strict"],
    ],
)
def test_hybrid_runs_only_the_frozen_system_on_test(
    args: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert hybrid.main(["out", *args, "--test"]) == 2
    assert "only the frozen system" in capsys.readouterr().out


def test_hybrid_runs_test_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-used")
    done = tmp_path / f"hybrid_general_claude-opus-5-5_{PROMPT_VERSION}"
    done.mkdir()
    (done / "viator-partner.yaml").write_text("[]\n")
    assert hybrid.main([str(tmp_path), "claude-opus-5-5", "general", "--test"]) == 2
    assert "runs once" in capsys.readouterr().out


def test_sealed_gold_checks_the_corrected_copy_on_its_own(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seal(tmp_path, monkeypatch, ["a.yaml"])
    fixed = tmp_path / "fixed"
    fixed.mkdir()
    (fixed / "a.yaml").write_text("fixed\n")
    monkeypatch.setattr(testset, "CORRECTED_DIR", fixed)
    with pytest.raises(SystemExit, match="not frozen"):
        sealed_gold(corrected=True)
    (fixed / "frozen.json").write_text(json.dumps(freeze(fixed, {})))
    assert sealed_gold(corrected=True) == [fixed / "a.yaml"]


def test_report_scores_the_corrected_copy_only_on_test(capsys: pytest.CaptureFixture[str]) -> None:
    from padan import report

    assert report.main(["pred", "--corrected"]) == 2
    assert "usage" in capsys.readouterr().out
