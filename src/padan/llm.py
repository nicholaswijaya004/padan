"""M2: Claude labels the fields the rules leave blank (ADR-001; Day 10 decisions D1-D6).

One call per field. The system prompt (schema, escalation policy, transform vocabulary) is the same
for every call and cached; the user message is one field with its evidence and sibling names. Every
reply is stored on disk by (model, prompt version, message), so re-running costs nothing unless the
model, the prompt or the field changes (D5).
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from padan.baselines import Field
from padan.enums import ENUM_VALUES
from padan.labels import VALID_TARGETS
from padan.schema import Booking
from padan.score import CRITICAL
from padan.transforms import TRANSFORMS

PROMPT_VERSION = (
    "v2"  # bump on any change to SYSTEM_PROMPT or field_message(): old replies are not reused
)
CACHE_DIR = Path("data/llm_cache")
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# $ per million tokens: (input, cache read, output). Cache writes cost 1.25x input.
PRICES: dict[str, tuple[float, float, float]] = {
    "claude-opus-5-5": (4.00, 0.20, 20.00),
    "claude-sonnet-5-5": (2.00, 0.20, 10.00),
    "claude-haiku-5-5": (0.10, 0.01, 0.50),
}

REPLY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["map", "none", "ask"]},
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"target": {"type": "string"}, "transform": {"type": "string"}},
                "required": ["target", "transform"],
                "additionalProperties": False,
            },
        },
        "candidate": {"type": "string"},
        "question": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["decision", "mappings", "candidate", "question", "reason"],
    "additionalProperties": False,
}


def _descriptions() -> dict[str, str]:
    """Target path -> description, from the schema's Field metadata."""
    from pydantic import BaseModel

    from padan.labels import _unwrap

    found: dict[str, str] = {}

    def walk(model: type[BaseModel], prefix: str) -> None:
        for name, info in model.model_fields.items():
            path, annotation = f"{prefix}{name}", _unwrap(info.annotation)
            if getattr(annotation, "__origin__", None) is list:
                path, (annotation,) = f"{path}[]", annotation.__args__
            if info.description:
                found[path] = info.description
            if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                walk(annotation, f"{path}.")

    walk(Booking, "")
    return found


# v2: v1 left this target out, so Claude could not map a partner's echo of our own reference.
OUR_REFERENCE = (
    "padan's own booking reference, which we send to the partner and the partner echoes back "
    "(e.g. reseller reference, client reference, partner reference)."
)


def schema_table() -> str:
    """One line per valid target: path, critical flag, allowed values, description. Sorted."""
    descriptions = _descriptions()
    lines = []
    for target in sorted(VALID_TARGETS):
        if target == "our_booking_id":
            lines.append(f"- {target}: {OUR_REFERENCE}")
            continue
        flags = " [critical]" if target in CRITICAL else ""
        values = ENUM_VALUES.get(target)
        allowed = f" Allowed values: {', '.join(sorted(values))}." if values else ""
        lines.append(f"- {target}{flags}: {descriptions.get(target, '')}{allowed}")
    return "\n".join(lines)


def _reflow(text: str) -> str:
    """Join hard-wrapped lines: a paragraph or a "- " bullet becomes one line."""
    lines: list[str] = []
    for line in text.strip().split("\n"):
        if line and lines and lines[-1] and not line.startswith(("- ", "#", "{")):
            lines[-1] += " " + line
        else:
            lines.append(line)
    return "\n".join(lines)


PROMPT = """
You map one field of a travel partner's booking API onto padan's canonical booking schema. Your
answer becomes a label in an integration that books real trips, so a wrong value in a critical field
is worse than an honest question to the partner.

## The canonical schema

A booking holds items[] (what was bought: product, option, dates, activity or cruise details) and,
once per booking, the identifiers, status, contact, travellers[], prices, cancellation terms and
fulfilment[] (vouchers and tickets). Paths use [] for list items. For fulfilment, name the document
kind in the path: fulfilment[kind=voucher].value or fulfilment[kind=ticket].format.

{schema}

## How to decide

- decision "map": the field carries the value of one target, possibly after a transform. Give one
mapping, or two when one partner value fills two targets (a date-time split into a date and a time).
- decision "none": the field carries nothing the schema holds: message metadata (correlation IDs,
versions, timestamps of the message), catalogue data repeated inside the booking, partner-internal
codes, or a value the schema has no place for.
- An identifier the client generates and sends, such as an idempotency key or a request UUID, is not
the partner's booking ID; choose none, unless the documentation says it is our booking reference.
- decision "ask": the field probably carries a critical target, but the documentation does not say
enough to fill it correctly. Examples: several amounts and nothing says which is the gross total; a
status given as numeric codes with no list of meanings; a date whose role is not stated. Give the
target you would map as "candidate" and the question for the partner. Never guess a critical field.
- An enum target (one with allowed values) needs transform enum_map(CODE=value, ...) covering every
code the documentation lists and every value in "Allowed values in the spec", read from each code's
description, not from its spelling: a partner's
PENDING can mean confirmed. If the codes are not documented, ask (critical target) or choose none.
- Use only the information given. A field with only an example value can still be mapped when its
name, example and neighbours make the meaning clear.

## Transforms

Leave transform "" when the value is copied as is. Otherwise use exactly one of: {transforms}.
- date_part, time_part: the date or the local time of a date-time.
- unix_seconds_to_datetime: epoch seconds to a date-time.
- minor_units_to_decimal(currencyField): 12345 cents to 123.45.
- to_e164: a phone number to +<country><number>.
- enum_map(CODE=value, ...): partner codes to allowed values.
- construct(key=value, ...): the value plus constants for its sibling fields, e.g.
construct(kind=voucher, format=pdf_url).

## Answer

Reply with the JSON object only. "mappings" is empty unless decision is "map"; "candidate" and
"question" are "" unless decision is "ask"; "reason" is one sentence.
"""

SYSTEM_PROMPT = _reflow(PROMPT).format(
    schema=schema_table(), transforms=", ".join(sorted(TRANSFORMS))
)


def siblings(field: Field, fields: list[Field]) -> list[str]:
    """Other fields in the same object (same endpoint, direction and parent path)."""
    endpoint, direction, path, _ = field
    parent = path.rsplit(".", 1)[0] if "." in path else ""
    found = []
    for other_endpoint, other_direction, other_path, _ in fields:
        other_parent = other_path.rsplit(".", 1)[0] if "." in other_path else ""
        same_object = (other_endpoint, other_direction, other_parent) == (
            endpoint,
            direction,
            parent,
        )
        if same_object and other_path != path:
            found.append(other_path.rsplit(".", 1)[-1])
    return found


def field_message(field: Field, fields: list[Field], listed: Sequence[str] = ()) -> str:
    """The user message for one field. `listed`: the spec's `enum` for it, when there is one."""
    endpoint, direction, path, evidence = field
    neighbours = ", ".join(siblings(field, fields)) or "(none)"
    allowed = f"\nAllowed values in the spec: {', '.join(listed)}" if listed else ""
    return (
        f"Endpoint: {endpoint} ({direction})\n"
        f"Field: {path}\n"
        f"Documentation: {evidence}{allowed}\n"
        f"Other fields in the same object: {neighbours}"
    )


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    output_tokens: int = 0
    cached_reply: bool = False  # served from the disk cache: no API call, no cost

    @property
    def dollars(self) -> float | None:
        if self.cached_reply:
            return 0.0
        price = PRICES.get(self.model)
        if price is None:
            return None  # a fallback model we have no price for; tokens are still recorded
        input_price, read_price, output_price = price
        return (
            self.input_tokens * input_price
            + self.cache_read_tokens * read_price
            + self.cache_write_tokens * input_price * 1.25
            + self.output_tokens * output_price
        ) / 1_000_000


class Client(Protocol):
    """The part of anthropic.Anthropic padan uses; tests pass a fake."""

    @property
    def beta(self) -> Any: ...


REFUSED = {
    "decision": "ask",
    "mappings": [],
    "candidate": "",
    "question": "Confirm what this field contains; the automated mapper declined it.",
    "reason": "The model declined this request.",
}


class Mapper:
    """Asks Claude about one field at a time, with a disk cache in front."""

    def __init__(self, client: Client, model: str, cache_dir: Path = CACHE_DIR) -> None:
        self.client, self.model = client, model
        self.cache = cache_dir / model / PROMPT_VERSION

    def ask(self, message: str) -> tuple[dict[str, Any], Usage]:
        key = hashlib.sha256(message.encode()).hexdigest()[:32]
        path = self.cache / f"{key}.json"
        if path.exists():
            stored = json.loads(path.read_text())
            return stored["reply"], Usage(model=stored["model"], cached_reply=True)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            output_config={
                "effort": "medium",
                "format": {"type": "json_schema", "schema": REPLY_SCHEMA},
            },
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=[
                {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
            ],
            messages=[{"role": "user", "content": message}],
        )
        usage = Usage(
            model=response.model,
            input_tokens=response.usage.input_tokens or 0,
            cache_read_tokens=response.usage.cache_read_input_tokens or 0,
            cache_write_tokens=response.usage.cache_creation_input_tokens or 0,
            output_tokens=response.usage.output_tokens or 0,
        )
        if response.stop_reason == "refusal":
            reply = dict(REFUSED)
        else:
            text = next(block.text for block in response.content if block.type == "text")
            reply = json.loads(text)
        self.cache.mkdir(parents=True, exist_ok=True)
        stored = {"model": response.model, "message": message, "reply": reply, "usage": vars(usage)}
        path.write_text(json.dumps(stored, indent=1) + "\n")
        return reply, usage
