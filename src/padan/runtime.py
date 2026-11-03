"""What generated clients import: reading partner paths and writing canonical ones (M3).

Paths are the label paths: dotted names, `[]` for every element of a list, `[n]` for one position
and `[key=value]` for the elements whose key has that value. Reading flattens:
`items[].travellers[].x` gives every traveller's `x` across all items, in order. Writing into a
canonical record follows one rule: the first list level in the target takes value i into element i
(a `[key=value]` level counts only the elements with that value, and gives new ones that value);
deeper list levels get one new element per value. A target with no list level takes the first value
only.
"""

import re
from typing import Any

PART = re.compile(r"^(?P<name>[^\[\]]*)(?:\[(?P<select>[^\]]*)\])?$")
Record = dict[str, Any]


def parts(path: str) -> list[tuple[str, str | None]]:
    """'a.b[].c[k=v]' -> [('a', None), ('b', ''), ('c', 'k=v')]."""
    found = []
    for part in path.split("."):
        match = PART.fullmatch(part)
        if match is None:
            raise ValueError(f"not a label path part: {part!r} in {path!r}")
        found.append((match["name"], match["select"]))
    return found


def selected(items: list[Any], select: str) -> list[Any]:
    """The list elements a selector keeps: all, one position, or those with key == value."""
    if select == "":
        return items
    if select.isdigit():
        return items[int(select) : int(select) + 1]
    key, _, value = select.partition("=")
    return [item for item in items if isinstance(item, dict) and str(item.get(key)) == value]


def get(payload: Any, path: str) -> list[Any]:
    """Every value at `path` in a partner payload, flattened over list levels; missing skipped."""
    values = [payload]
    for name, select in parts(path):
        found: list[Any] = []
        for value in values:
            if name:
                if not isinstance(value, dict) or name not in value:
                    continue
                value = value[name]
            if select is None:
                found.append(value)
            elif isinstance(value, list):
                found += selected(value, select)
        values = found
    return [value for value in values if value is not None]


def constant(select: str) -> Record:
    """What a new list element gets from its selector: [kind=voucher] -> {'kind': 'voucher'}."""
    key, sep, value = select.partition("=")
    return {key: value} if sep else {}


def put(record: Record, path: str, values: list[Any]) -> None:
    """Write `values` at a canonical path, by the rule in the module docstring."""
    *inner, (last, last_select) = parts(path)
    has_list = any(select is not None for _, select in inner) or last_select is not None
    for i, value in enumerate(values if has_list else values[:1]):
        node, first = record, True
        for name, select in inner:
            if select is None:
                node = node.setdefault(name, {})
                continue
            elements: list[Record] = node.setdefault(name, [])
            if first:
                first = False
                matching = selected(elements, select)
                if i < len(matching):
                    node = matching[i]
                    continue
            node = constant(select)
            elements.append(node)
        if last_select is None:
            node[last] = value
        else:
            node.setdefault(last, []).append(value)
