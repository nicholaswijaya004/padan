"""Rule engine (M1): partner fields -> prediction label files, scored with leave-one-spec-out.

For each field: find candidates (padan.candidates), then decide() turns them into labels under the
escalation policy (E2). Every prediction gets a receipt naming the lexicon entries behind it (E5).

    python -m padan.engine OUT_DIR    # writes OUT_DIR/rules_strict/ and OUT_DIR/rules_general/
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args, get_origin

from pydantic import BaseModel

from padan.baselines import Field, dump, fields_of, gold_files
from padan.candidates import Candidate, Lexicon, candidates, load_lexicon
from padan.labels import ASK_PARTNER, NONE, LabelEntry, Source, _unwrap, load_labels, normalise
from padan.schema import Booking
from padan.score import CRITICAL


@dataclass(frozen=True)
class Decision:
    target: str  # a canonical target, NONE or ASK_PARTNER
    kind: Literal["direct", "transform"] | None = None
    transform: str | None = None
    candidate: str | None = None  # for ASK_PARTNER: the target we would map if the partner confirms


def enum_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    """Targets whose values are a fixed set (Literal): a raw partner code is not a valid value."""
    paths: set[str] = set()
    for name, info in model.model_fields.items():
        path, annotation = f"{prefix}{name}", _unwrap(info.annotation)
        if get_origin(annotation) is list:
            path, (annotation,) = f"{path}[]", get_args(annotation)
        if get_origin(annotation) is Literal:
            paths.add(path)
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            paths |= enum_paths(annotation, f"{path}.")
    return paths


ENUMS = frozenset(enum_paths(Booking))


def is_critical_target(target: str) -> bool:
    return normalise(target) in CRITICAL


def needs_enum_map(target: str) -> bool:
    return normalise(target) in ENUMS


def decide(found: list[Candidate]) -> list[Decision]:
    """The escalation policy: candidates -> one decision per target (E2). You write this."""
    # 1. nothing matched: leave it blank
    if not found:
        return [Decision(NONE)]
    # 2. learnt from an ASK_PARTNER label: the meaning was not documented, so ask
    for candidate in found:
        if candidate.escalate:
            return [Decision(ASK_PARTNER, candidate=candidate.targets[0])]
    # 3. two different readings: ask if a critical field is at stake, else leave it blank
    readings = {candidate.targets for candidate in found}
    if len(readings) > 1:
        critical = [t for targets in sorted(readings) for t in targets if is_critical_target(t)]
        return [Decision(ASK_PARTNER, candidate=critical[0])] if critical else [Decision(NONE)]
    # 4. one reading: map every target, with its transform if the entry has one
    best = found[0]
    decisions = []
    for i, target in enumerate(best.targets):
        transform = best.transforms[i] if best.transforms else None
        if transform is not None:
            decisions.append(Decision(target, "transform", transform))
        elif needs_enum_map(target) and is_critical_target(target):
            # a raw partner code in a critical enum (status) is a silent wrong value: ask
            return [Decision(ASK_PARTNER, candidate=target)]
        else:
            decisions.append(Decision(target, "direct"))
    return decisions


def question(candidate: str | None) -> str:
    return f"Does this field carry {candidate}? Its meaning or values are not documented."


def predict(
    fields: list[Field], lexicon: Lexicon, off: list[str]
) -> tuple[list[LabelEntry], list[dict[str, Any]]]:
    """Prediction entries for every field, plus a receipt per field (which entries matched)."""
    entries: list[LabelEntry] = []
    receipts: list[dict[str, Any]] = []
    for endpoint, direction, path, evidence in fields:
        found = candidates(path, lexicon, off)
        decisions = decide(found)
        for d in decisions:
            entries.append(
                LabelEntry(
                    source=Source(endpoint=endpoint, direction=direction, paths=[path]),  # type: ignore[arg-type]
                    target=d.target,
                    kind=d.kind,
                    transform=d.transform,
                    candidate=d.candidate,
                    question=question(d.candidate) if d.target == ASK_PARTNER else None,
                    evidence=evidence,
                )
            )
        receipts.append(
            {
                "endpoint": endpoint,
                "path": path,
                "decided": [d.target for d in decisions],
                "entries": [c.entry for c in found],
            }
        )
    return entries, receipts


VARIANTS = {"rules_strict": ["general"], "rules_general": []}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m padan.engine OUT_DIR")
        return 2
    out, lexicon = Path(argv[0]), load_lexicon()
    for variant, extra_off in VARIANTS.items():
        (out / variant).mkdir(parents=True, exist_ok=True)
        for gold_path in gold_files():
            spec = gold_path.stem
            fields = fields_of(load_labels(gold_path))
            entries, receipts = predict(fields, lexicon, off=[spec, *extra_off])
            (out / variant / gold_path.name).write_text(dump(entries))
            (out / variant / f"{spec}.rules.json").write_text(json.dumps(receipts, indent=1) + "\n")
    print(
        f"wrote {', '.join(VARIANTS)} (leave-one-spec-out) for {len(gold_files())} specs to {out}/"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
