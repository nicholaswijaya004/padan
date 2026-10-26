"""The Claude call: prompt, request shape, disk cache and cost. Uses a fake client: no spend."""

from pathlib import Path

import pytest

from padan.labels import VALID_TARGETS
from padan.llm import PROMPT_VERSION, SYSTEM_PROMPT, Mapper, Usage, field_message, siblings
from tests.fake_claude import REFUSE, FakeClient, reply

EP = "PUT /bookings"
FIELDS = [
    (EP, "request", "holder.name", "[no description; example: Ana]"),
    (EP, "request", "holder.surname", "[no description; example: Lim]"),
    (EP, "request", "clientReference", "[no description; example: X1]"),
]


def test_the_prompt_lists_every_partner_target_with_flags_and_values() -> None:
    for target in VALID_TARGETS - {"our_booking_id"}:
        assert f"- {target}" in SYSTEM_PROMPT
    assert "- our_booking_id" not in SYSTEM_PROMPT  # set by padan, never by a partner
    assert "- status [critical]:" in SYSTEM_PROMPT
    assert "Allowed values: cancelled, confirmed, failed, on_hold, pending." in SYSTEM_PROMPT
    assert "enum_map" in SYSTEM_PROMPT and "PENDING can mean confirmed" in SYSTEM_PROMPT


def test_the_field_message_names_its_siblings_only() -> None:
    assert siblings(FIELDS[0], FIELDS) == ["surname"]
    message = field_message(FIELDS[0], FIELDS)
    assert "Field: holder.name" in message and "same object: surname" in message
    assert "clientReference" not in message


def test_the_request_pins_model_effort_format_fallback_and_caching(tmp_path: Path) -> None:
    client = FakeClient([reply("none")])
    Mapper(client, "claude-opus-5-5", tmp_path).ask("Field: x")
    [request] = client.calls
    assert request["model"] == "claude-opus-5-5"
    assert request["output_config"]["effort"] == "medium"
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert request["fallbacks"] == "default" and request["betas"]
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert request["system"][0]["text"] == SYSTEM_PROMPT


def test_a_second_identical_question_is_answered_from_disk(tmp_path: Path) -> None:
    client = FakeClient([reply("map", ("contact.given_name", ""))])
    mapper = Mapper(client, "claude-opus-5-5", tmp_path)
    first, paid = mapper.ask("Field: holder.name")
    second, free = mapper.ask("Field: holder.name")
    assert first == second and len(client.calls) == 1
    assert paid.dollars == pytest.approx(0.0118) and free.dollars == 0.0
    assert (tmp_path / "claude-opus-5-5" / PROMPT_VERSION).is_dir()


def test_a_new_prompt_version_or_model_is_not_served_from_old_replies(tmp_path: Path) -> None:
    Mapper(FakeClient([reply("none")]), "claude-opus-5-5", tmp_path).ask("Field: x")
    sonnet = FakeClient([reply("none")])
    Mapper(sonnet, "claude-sonnet-5-5", tmp_path).ask("Field: x")
    assert len(sonnet.calls) == 1


def test_a_refusal_becomes_a_question_for_the_partner(tmp_path: Path) -> None:
    answer, _ = Mapper(FakeClient([REFUSE]), "claude-opus-5-5", tmp_path).ask("Field: x")
    assert answer["decision"] == "ask"


def test_cost_from_tokens_and_unknown_models() -> None:
    usage = Usage("claude-sonnet-5-5", input_tokens=300, cache_read_tokens=3000, output_tokens=500)
    assert usage.dollars == pytest.approx((300 * 2 + 3000 * 0.2 + 500 * 10) / 1e6)
    assert Usage("claude-opus-4-8", input_tokens=1).dollars is None  # a fallback without a price
    write = Usage("claude-opus-5-5", cache_write_tokens=1000)
    assert write.dollars == pytest.approx(1000 * 4 * 1.25 / 1e6)
