"""R4: translation tables (enum_map) for enum targets, built from the values a partner documents.

A partner code is matched to our value by name (`QRCODE` -> qrcode). The table is built only when
every documented code matches; a partial table would leave a real value without a translation.
"""

import re
from collections.abc import Sequence
from typing import Literal, get_args, get_origin

from pydantic import BaseModel

from padan.labels import _unwrap, normalise
from padan.schema import Booking


def enum_values(model: type[BaseModel], prefix: str = "") -> dict[str, frozenset[str]]:
    """Every enum target and its allowed values, e.g. {"status": {"on_hold", "pending", ...}}."""
    found: dict[str, frozenset[str]] = {}
    for name, info in model.model_fields.items():
        path, annotation = f"{prefix}{name}", _unwrap(info.annotation)
        if get_origin(annotation) is list:
            path, (annotation,) = f"{path}[]", get_args(annotation)
        if get_origin(annotation) is Literal:
            found[path] = frozenset(get_args(annotation))
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            found |= enum_values(annotation, f"{path}.")
    return found


ENUM_VALUES = enum_values(Booking)

# A code in backticks, all capitals: `ON_HOLD`, `PDF_URL`, `ADULT`
CODE = re.compile(r"`([A-Z][A-Z0-9_]*)`")


def enum_map_from(evidence: str, target: str, listed: Sequence[str] = ()) -> str | None:
    """'`ADULT`, `CHILD`' for travellers[].traveller_type -> 'enum_map(ADULT=adult, CHILD=child)'.

    `listed` adds the codes the spec's `enum` lists, which the description may leave out.
    None when no codes are documented, or when any code has no value of the same name.
    """
    allowed = ENUM_VALUES[normalise(target)]
    codes = list(dict.fromkeys([*CODE.findall(evidence), *listed]))  # each code once, in order
    if not codes:
        return None
    pairs = [(code, code.lower()) for code in codes]
    if any(value not in allowed for _, value in pairs):
        return None
    return "enum_map(" + ", ".join(f"{code}={value}" for code, value in pairs) + ")"
