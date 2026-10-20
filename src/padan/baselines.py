"""Baselines every mapping system must beat, written as prediction files the scorer reads.

The source fields come from the gold files (the coverage test proves they equal Stage 1's fields),
with filters dropped, so a baseline never gets a split like inputFields[id=EMAIL] for free.

    python -m padan.baselines OUT_DIR    # writes OUT_DIR/<baseline>/<spec>.yaml
"""

import re
import sys
from collections.abc import Callable
from pathlib import Path

import yaml

from padan.labels import NONE, VALID_TARGETS, LabelEntry, Source, load_labels, normalise

LABEL_DIR = Path("data/labels")
Field = tuple[str, str, str, str]  # endpoint, direction, path, evidence


def gold_files(label_dir: Path = LABEL_DIR) -> list[Path]:
    return sorted(p for p in label_dir.glob("*.yaml") if p.name != "dry_run.yaml")


def fields_of(gold: list[LabelEntry]) -> list[Field]:
    """Each source field once, in gold order, with filters and positions read as []."""
    seen: dict[tuple[str, str, str], str] = {}
    for entry in gold:
        for path in entry.source.paths:
            key = (entry.source.endpoint, entry.source.direction, normalise(path))
            seen.setdefault(key, entry.evidence)
    return [(*key, evidence) for key, evidence in seen.items()]


def leaf(path: str) -> str:
    """'ReservationID@BookedDate' -> 'bookeddate'; 'travellers[].given_name' -> 'givenname'."""
    name = re.split(r"[.@]", path.replace("[]", ""))[-1]
    return name.replace("_", "").lower()


TARGETS_BY_LEAF: dict[str, list[str]] = {}
for _target in sorted(VALID_TARGETS):
    TARGETS_BY_LEAF.setdefault(leaf(_target), []).append(_target)


def entry(field: Field, target: str) -> LabelEntry:
    endpoint, direction, path, evidence = field
    return LabelEntry(
        source=Source(endpoint=endpoint, direction=direction, paths=[path]),  # type: ignore[arg-type]
        target=target,
        kind=None if target == NONE else "direct",
        evidence=evidence,
    )


def all_none(fields: list[Field]) -> list[LabelEntry]:
    """Map nothing: the floor. F1 is 0 or undefined, and it can make no critical error."""
    return [entry(field, NONE) for field in fields]


def name_match(fields: list[Field]) -> list[LabelEntry]:
    """Map a field when its last name equals exactly one canonical field's (case and _ ignored)."""
    predicted = []
    for field in fields:
        matches = TARGETS_BY_LEAF.get(leaf(field[2]), [])
        predicted.append(entry(field, matches[0] if len(matches) == 1 else NONE))
    return predicted


BASELINES: dict[str, Callable[[list[Field]], list[LabelEntry]]] = {
    "all_none": all_none,
    "name_match": name_match,
}


def dump(entries: list[LabelEntry]) -> str:
    rows = [e.model_dump(mode="json", exclude_none=True) for e in entries]
    return yaml.safe_dump(rows, sort_keys=False, allow_unicode=True, width=1000)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m padan.baselines OUT_DIR")
        return 2
    out = Path(argv[0])
    for name, baseline in BASELINES.items():
        (out / name).mkdir(parents=True, exist_ok=True)
        for path in gold_files():
            predicted = baseline(fields_of(load_labels(path)))
            (out / name / path.name).write_text(dump(predicted))
    print(f"wrote {', '.join(BASELINES)} for {len(gold_files())} specs to {out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
