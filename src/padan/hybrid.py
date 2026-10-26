"""M2 hybrid: rules first; Claude labels only what the rules leave blank, plus `status` (D1).

    uv run --env-file .env python -m padan.hybrid OUT_DIR MODEL BASE [SPEC ...]
    # e.g. data/predictions claude-opus-5-5 strict hotelbeds-activities

Writes OUT_DIR/hybrid_<base>_<model>/<spec>.yaml (label files the scorer reads) and a cost report.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from padan.baselines import Field, dump, fields_of, gold_files
from padan.candidates import Lexicon, load_lexicon
from padan.engine import VARIANTS, predict, question
from padan.labels import ASK_PARTNER, NONE, LabelEntry, Source, load_labels
from padan.llm import Mapper, Usage, field_message


def entry(field: Field, target: str, **extra: Any) -> LabelEntry:
    endpoint, direction, path, evidence = field
    return LabelEntry(
        source=Source(endpoint=endpoint, direction=direction, paths=[path]),  # type: ignore[arg-type]
        target=target,
        evidence=evidence,
        **extra,
    )


def to_labels(reply: dict[str, Any], field: Field) -> tuple[list[LabelEntry], bool]:
    """Claude's reply -> label entries, and whether the reply was valid.

    An invalid reply (unknown target, unknown transform, "map" with no mapping) becomes NONE:
    a blank is visible and safe; a malformed label is not.
    """
    try:
        if reply["decision"] == "none":
            return [entry(field, NONE)], True
        if reply["decision"] == "ask":
            candidate = reply["candidate"] or None
            text = reply["question"] or question(candidate)
            return [entry(field, ASK_PARTNER, candidate=candidate, question=text)], True
        if not reply["mappings"]:
            return [entry(field, NONE)], False
        labels = []
        for mapping in reply["mappings"]:
            transform = mapping["transform"] or None
            kind = "transform" if transform is not None else "direct"
            labels.append(entry(field, mapping["target"], kind=kind, transform=transform))
        return labels, True
    except (ValidationError, KeyError, ValueError):
        return [entry(field, NONE)], False


def needs_claude(labels: list[LabelEntry]) -> bool:
    """D1: the rules left the field blank, or asked about `status` only because of its codes."""
    targets = {label.target for label in labels}
    if targets == {NONE}:
        return True
    return targets == {ASK_PARTNER} and labels[0].candidate == "status"


def hybrid(
    fields: list[Field], lexicon: Lexicon, off: list[str], mapper: Mapper
) -> tuple[list[LabelEntry], list[Usage], int]:
    """Rule labels, with Claude's labels for the fields the rules could not decide."""
    rule_labels, _ = predict(fields, lexicon, off)
    by_field: dict[tuple[str, str, str], list[LabelEntry]] = {}
    for label in rule_labels:
        key = (label.source.endpoint, label.source.direction, label.source.paths[0])
        by_field.setdefault(key, []).append(label)
    labels: list[LabelEntry] = []
    usages: list[Usage] = []
    invalid = 0
    for field in fields:
        mine = by_field[(field[0], field[1], field[2])]
        if not needs_claude(mine):
            labels += mine
            continue
        reply, usage = mapper.ask(field_message(field, fields))
        usages.append(usage)
        claude_labels, valid = to_labels(reply, field)
        invalid += not valid
        labels += claude_labels
    return labels, usages, invalid


def cost_report(usages: list[Usage], invalid: int) -> dict[str, Any]:
    called = [u for u in usages if not u.cached_reply]
    dollars = [u.dollars for u in called]
    return {
        "fields_sent": len(usages),
        "api_calls": len(called),
        "from_disk_cache": len(usages) - len(called),
        "invalid_replies": invalid,
        "input_tokens": sum(u.input_tokens for u in called),
        "cache_read_tokens": sum(u.cache_read_tokens for u in called),
        "cache_write_tokens": sum(u.cache_write_tokens for u in called),
        "output_tokens": sum(u.output_tokens for u in called),
        "dollars": None if None in dollars else round(sum(d or 0 for d in dollars), 4),
        "models": sorted({u.model for u in called}),
    }


def main(argv: list[str]) -> int:
    if len(argv) < 3 or f"rules_{argv[2]}" not in VARIANTS:
        print("usage: python -m padan.hybrid OUT_DIR MODEL strict|general [SPEC ...]")
        return 2
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ANTHROPIC_API_KEY is not set: run with `uv run --env-file .env ...` (see make hybrid)"
        )
        return 2
    import anthropic

    out_dir, model, base, specs = Path(argv[0]), argv[1], argv[2], set(argv[3:])
    out = out_dir / f"hybrid_{base}_{model}"
    out.mkdir(parents=True, exist_ok=True)
    mapper, lexicon = Mapper(anthropic.Anthropic(), model), load_lexicon()
    report: dict[str, Any] = {}
    for gold_path in gold_files():
        spec = gold_path.stem
        if specs and spec not in specs:
            continue
        fields = fields_of(load_labels(gold_path))
        off = [spec, *VARIANTS[f"rules_{base}"]]
        labels, usages, invalid = hybrid(fields, lexicon, off, mapper)
        (out / gold_path.name).write_text(dump(labels))
        report[spec] = cost_report(usages, invalid)
        print(f"{spec}: {json.dumps(report[spec])}")
    (out / "cost.json").write_text(json.dumps(report, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
