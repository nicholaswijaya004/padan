"""Transform vocabulary: the functions a `transform` label may name, parsed so they can be compared.

Only kind=transform uses the vocabulary. kind=derived keeps a free-text recipe (several inputs,
lookups, conditions) and is scored on its target only.
"""

import re
from dataclasses import dataclass

TRANSFORMS = frozenset(
    {
        "date_part",  # datetime -> date
        "time_part",  # datetime -> time
        "unix_seconds_to_datetime",
        "minor_units_to_decimal",  # 12345 cents -> 123.45, argument: the currency field
        "to_e164",  # phone number -> +6281234567890
        "enum_map",  # partner code -> canonical value, e.g. enum_map(ADULT=adult, CHILD=child)
        "construct",  # value plus constants for its siblings, e.g. construct(format=pdf_url)
    }
)

CALL = re.compile(r"(?P<name>\w+)(?:\((?P<args>.*)\))?")


@dataclass(frozen=True)
class Transform:
    name: str
    # (key, value) pairs; a positional argument has key "". Keyword arguments are sorted by key,
    # so enum_map(A=x, B=y) == enum_map(B=y, A=x); positional ones keep their order.
    args: tuple[tuple[str, str], ...] = ()


def parse_transform(text: str) -> Transform:
    """'enum_map(ADULT=adult, CHILD=child)' -> Transform('enum_map', (('ADULT', 'adult'), ...))."""
    match = CALL.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"transform {text!r} is not `name` or `name(args)`")
    name = match["name"]
    if name not in TRANSFORMS:
        raise ValueError(f"unknown transform {name!r}; known: {', '.join(sorted(TRANSFORMS))}")
    args: list[tuple[str, str]] = []
    for part in (match["args"] or "").split(","):
        if not part.strip():
            continue
        key, sep, value = part.partition("=")
        args.append((key.strip(), value.strip()) if sep else ("", key.strip()))
    keys = [key for key, _ in args if key]
    if len(keys) != len(set(keys)):
        raise ValueError(f"transform {text!r} repeats an argument")
    return Transform(name, tuple(sorted(args, key=lambda arg: arg[0])))
