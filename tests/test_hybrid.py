"""M2 hybrid: which fields go to Claude, how its replies become labels, and the cost report."""

from pathlib import Path

from padan.candidates import Lexicon
from padan.hybrid import cost_report, hybrid, main, needs_claude, to_labels
from padan.labels import LabelEntry
from padan.llm import Mapper, Usage
from tests.fake_claude import FakeClient, reply

EP = "GET /bookings/{id}"
FIELD = (EP, "response", "startDateTime", "Start, ISO 8601 local date-time.")


def label(target: str, candidate: str | None = None) -> LabelEntry:
    extra = {"question": "?", "candidate": candidate} if target == "ASK_PARTNER" else {}
    kind = None if target in ("NONE", "ASK_PARTNER") else "direct"
    return LabelEntry.model_validate(
        {
            "source": {"endpoint": EP, "direction": "response", "paths": ["x"]},
            "target": target,
            "kind": kind,
            "evidence": "-",
            **extra,
        }
    )


# --- to_labels(): you write this -----------------------------------------------------------------


def test_none_is_a_blank() -> None:
    labels, valid = to_labels(reply("none"), FIELD)
    assert [x.target for x in labels] == ["NONE"] and valid


def test_ask_keeps_the_candidate_and_question() -> None:
    labels, valid = to_labels(reply("ask", candidate="status", question="What is 42?"), FIELD)
    assert [(x.target, x.candidate, x.question) for x in labels] == [
        ("ASK_PARTNER", "status", "What is 42?")
    ]
    assert valid


def test_ask_without_a_candidate_gets_a_default_question() -> None:
    [only], valid = to_labels(reply("ask"), FIELD)
    assert only.candidate is None and only.question and valid


def test_a_direct_mapping() -> None:
    [only], valid = to_labels(reply("map", ("items[].product_id", "")), FIELD)
    assert (only.target, only.kind, only.transform) == ("items[].product_id", "direct", None)
    assert valid


def test_a_split_is_two_labels_with_transforms() -> None:
    answer = reply("map", ("items[].start_date", "date_part"), ("items[].start_time", "time_part"))
    labels, valid = to_labels(answer, FIELD)
    assert [(x.target, x.kind, x.transform) for x in labels] == [
        ("items[].start_date", "transform", "date_part"),
        ("items[].start_time", "transform", "time_part"),
    ]
    assert valid


def test_an_invented_target_becomes_a_blank_and_is_counted() -> None:
    labels, valid = to_labels(reply("map", ("booking.start", "")), FIELD)
    assert [x.target for x in labels] == ["NONE"] and not valid


def test_an_unknown_transform_becomes_a_blank_and_is_counted() -> None:
    labels, valid = to_labels(reply("map", ("items[].start_date", "to_date")), FIELD)
    assert [x.target for x in labels] == ["NONE"] and not valid


def test_map_with_no_mapping_is_a_blank_and_is_counted() -> None:
    labels, valid = to_labels(reply("map"), FIELD)
    assert [x.target for x in labels] == ["NONE"] and not valid


# --- which fields go to Claude (D1) ---------------------------------------------------------------


def test_blank_fields_and_status_questions_go_to_claude() -> None:
    assert needs_claude([label("NONE")])
    assert needs_claude([label("ASK_PARTNER", candidate="status")])
    assert not needs_claude([label("ASK_PARTNER", candidate="total_price.amount")])
    assert not needs_claude([label("items[].product_id")])


def test_hybrid_sends_only_what_the_rules_left_blank(tmp_path: Path) -> None:
    lexicon = Lexicon.model_validate(
        {
            "entities": {},
            "wrappers": [],
            "dependents": [],
            "entries": [
                {
                    "id": "pid",
                    "targets": ["items[].product_id"],
                    "leaf": [["product", "id"]],
                    "context": [""],
                    "learnt_from": ["other"],
                },
            ],
        }
    )
    fields = [(EP, "response", "productId", "-"), FIELD]
    answer = reply("map", ("items[].start_date", "date_part"), ("items[].start_time", "time_part"))
    client = FakeClient([answer])
    labels, usages, invalid = hybrid(
        fields, lexicon, [], Mapper(client, "claude-opus-5-5", tmp_path)
    )
    assert [x.target for x in labels] == [
        "items[].product_id",
        "items[].start_date",
        "items[].start_time",
    ]
    assert len(client.calls) == 1 and len(usages) == 1 and invalid == 0
    assert "Field: startDateTime" in client.calls[0]["messages"][0]["content"]


def test_cost_report_counts_calls_cache_and_dollars() -> None:
    usages = [
        Usage("claude-opus-5-5", input_tokens=300, cache_read_tokens=3000, output_tokens=500),
        Usage("claude-opus-5-5", cached_reply=True),
    ]
    report = cost_report(usages, invalid=1)
    assert (report["fields_sent"], report["api_calls"], report["from_disk_cache"]) == (2, 1, 1)
    assert report["dollars"] == 0.0118 and report["invalid_replies"] == 1


def test_main_refuses_to_run_without_a_key(monkeypatch, tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main([str(tmp_path), "claude-opus-5-5", "strict"]) == 2
    assert "ANTHROPIC_API_KEY is not set" in capsys.readouterr().out  # valid arguments, missing key


def test_main_rejects_an_unknown_base(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["out", "claude-opus-5-5", "loose"]) == 2
    assert "usage:" in capsys.readouterr().out
