"""Test labels from the canonical side (ADR-001 Amendments 4 and 6).

1. `new SPEC` writes a sheet with one row per canonical target. The labeller lists under each target
   the partner field(s) that carry it (`picks`), or asks the partner. No model is involved.
2. `fill SPEC` turns the sheet into an ordinary label file: picked fields get their target, every
   other scoped field gets NONE, so the validator and the scorer work unchanged.
3. `freeze` records the SHA-256 of every test label file and sheet: a frozen file may not change.
"""

import json
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, TypeAdapter, field_validator, model_validator

from padan.extract import ExtractedField, load_scoped, quote, scoped_fields
from padan.fetch import sha256_hex
from padan.labels import ASK_PARTNER, NONE, VALID_TARGETS, Source, load_labels, normalise
from padan.llm import _descriptions
from padan.score import CRITICAL

TEST_DIR = Path("data/labels/test")
SHEET_DIR = TEST_DIR / "sheets"
FROZEN = TEST_DIR / "frozen.json"

Key = tuple[str, str, str]  # (endpoint, direction, extracted path)


class Pick(BaseModel):
    """One partner field (or several, for a derived value) that carries the row's target."""

    source: Source
    kind: Literal["direct", "transform", "derived", "ask"]
    target: str | None = None  # a narrower form of the row's target: fulfilment[kind=voucher].value
    transform: str | None = None
    question: str | None = None


class Row(BaseModel):
    target: str
    picks: list[Pick] = []

    @field_validator("target")
    @classmethod
    def is_a_target(cls, target: str) -> str:
        if target not in VALID_TARGETS:
            raise ValueError(f"{target!r} is not a Booking schema path")
        return target

    @model_validator(mode="after")
    def picks_narrow_the_target(self) -> "Row":
        for pick in self.picks:
            if pick.target is not None and normalise(pick.target) != self.target:
                raise ValueError(f"{pick.target!r} is not a form of {self.target!r}")
        return self


ROWS = TypeAdapter(list[Row])

HEADER = """\
# Target-side sheet for {spec} (ADR-001 Amendments 4 and 6): labelled by hand, no model.
# For each canonical target, add the partner field(s) that carry it under `picks`; leave [] if none.
# A pick names an extracted field as the scaffold shows it (a filter like [id=EMAIL] is allowed):
#   picks:
#     - source: {{endpoint: 'POST /orders', direction: request, paths: ['customer.email']}}
#       kind: direct                # direct | transform | derived | ask
#       target: ''                  # optional: the row's target with a filter, e.g. on a fulfilment
#                                   # row 'fulfilment[kind=voucher].value', as dev gold names it
#       transform: ''               # transform and derived only, e.g. 'to_e164'
#       question: ''                # ask only: the question for the partner (target = candidate)
# Every scoped field that no pick names becomes NONE when you run `make labels SPEC={spec}`.
"""


def render_sheet(spec_id: str) -> str:
    """One row per canonical target, sorted, with its critical flag and description as a comment."""
    descriptions = _descriptions()
    lines = [HEADER.format(spec=spec_id)]
    for target in sorted(VALID_TARGETS):
        flag = "[critical] " if target in CRITICAL else ""
        lines += [
            f"- target: {quote(target)}",
            f"  # {flag}{descriptions.get(target, '')}".rstrip(),
            "  picks: []",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


def key_of(field: ExtractedField) -> Key:
    return (field.endpoint, field.direction, field.path)


def label_for(target: str, pick: Pick, evidence: str) -> dict[str, Any]:
    """The label entry for a pick; `ask` becomes ASK_PARTNER, with the target as candidate."""
    entry: dict[str, Any] = {"source": pick.source.model_dump()}
    if pick.kind == "ask":
        entry |= {"target": ASK_PARTNER, "evidence": evidence}
        entry |= {"candidate": target, "question": pick.question or ""}
    else:
        entry |= {"target": target, "kind": pick.kind}
        if pick.transform:
            entry["transform"] = pick.transform
        entry["evidence"] = evidence
    return entry


def fill(rows: list[Row], fields: list[ExtractedField]) -> list[dict[str, Any]]:
    """Label entries in spec order: each pick at its first field, NONE for fields no pick names."""
    scoped = {key_of(field): field for field in fields}
    placed: dict[Key, list[dict[str, Any]]] = {}
    covered: set[Key] = set()
    for row in rows:
        for pick in row.picks:
            source = pick.source
            keys: list[Key] = [
                (source.endpoint, source.direction, normalise(path)) for path in source.paths
            ]
            for key in keys:
                if key not in scoped:
                    raise ValueError(f"{row.target}: {' '.join(key)} is not a scoped field")
            covered |= set(keys)
            first = keys[0]
            label = label_for(pick.target or row.target, pick, scoped[first].evidence)
            placed.setdefault(first, []).append(label)
    entries: list[dict[str, Any]] = []
    for field in fields:
        key = key_of(field)
        if key in placed:
            entries += placed[key]
        elif key not in covered:
            none = {"endpoint": field.endpoint, "direction": field.direction, "paths": [field.path]}
            entries.append({"source": none, "target": NONE, "evidence": field.evidence})
    return entries


def freeze(test_dir: Path, recorded: dict[str, str]) -> dict[str, str]:
    """Add every test file's hash to `recorded`. A file already frozen may not have changed."""
    hashes = dict(recorded)
    for path in sorted(test_dir.rglob("*.yaml")):
        name = path.relative_to(test_dir).as_posix()
        digest = sha256_hex(path.read_bytes())
        if name in recorded and recorded[name] != digest:
            raise ValueError(f"{name} changed after it was frozen")
        hashes[name] = digest
    return hashes


def verify(test_dir: Path, recorded: dict[str, str]) -> list[str]:
    """Check every frozen file still has its recorded hash; the problems, empty when all match."""
    problems = []
    for name, digest in sorted(recorded.items()):
        path = test_dir / name
        if not path.exists():
            problems.append(f"missing  {name}")
        elif sha256_hex(path.read_bytes()) != digest:
            problems.append(f"changed  {name}")
    return problems


def main(argv: list[str]) -> int:
    """`new SPEC` | `fill SPEC` | `freeze` | `verify`."""
    command, *rest = argv or [""]
    recorded: dict[str, str] = json.loads(FROZEN.read_text()) if FROZEN.exists() else {}
    if command == "new" and len(rest) == 1:
        sheet = SHEET_DIR / f"{rest[0]}.yaml"
        if sheet.exists():
            print(f"{sheet} exists; not overwriting your labels")
            return 1
        sheet.parent.mkdir(parents=True, exist_ok=True)
        sheet.write_text(render_sheet(rest[0]))
        print(f"wrote {sheet}")
        return 0
    if command == "fill" and len(rest) == 1:
        spec_id = rest[0]
        out = TEST_DIR / f"{spec_id}.yaml"
        if out.relative_to(TEST_DIR).as_posix() in recorded:
            print(f"{out} is frozen; not overwriting")
            return 1
        rows = ROWS.validate_python(yaml.safe_load((SHEET_DIR / f"{spec_id}.yaml").read_text()))
        entries = fill(rows, scoped_fields(load_scoped(spec_id)))
        header = (
            f"# Test labels for {spec_id}: generated by padan.sheet from sheets/{spec_id}.yaml.\n"
        )
        out.write_text(
            header + yaml.safe_dump(entries, sort_keys=False, allow_unicode=True, width=1000)
        )
        labels = load_labels(out)  # the same checks as every dev label file
        counts = {t: sum(1 for e in labels if e.target == t) for t in (NONE, ASK_PARTNER)}
        named = len(labels) - counts[NONE] - counts[ASK_PARTNER]
        print(
            json.dumps(
                {"spec": spec_id, "named": named, "ask": counts[ASK_PARTNER], "none": counts[NONE]}
            )
        )
        return 0
    if command == "freeze" and not rest:
        try:
            hashes = freeze(TEST_DIR, recorded)
        except ValueError as e:
            print(f"FAIL  {e}")
            return 1
        FROZEN.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n")
        print(f"froze {len(json.loads(FROZEN.read_text()))} file(s) in {FROZEN}")
        return 0
    if command == "verify" and not rest:
        problems = verify(TEST_DIR, recorded)
        for problem in problems:
            print(problem)
        print(f"{len(recorded)} frozen file(s), {len(problems)} problem(s)")
        return 1 if problems else 0
    print("usage: python -m padan.sheet new SPEC | fill SPEC | freeze | verify")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
