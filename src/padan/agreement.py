"""A second labeller on a sample of one test spec, and their agreement with the gold (Amendment 7).

`sample SPEC` draws the pre-registered stratified sample from the frozen gold and writes, for the
second labeller, a blank sheet of only those fields (the dev scaffold format: source and evidence,
target blank). `score SPEC FILE` compares their filled sheet with the frozen gold, field by field:
raw agreement and Cohen's kappa on the target, overall and per stratum.
"""

import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

from padan.extract import load_scoped, scoped_fields, write_scaffold
from padan.labels import ASK_PARTNER, NONE, load_labels, normalise
from padan.llm import schema_table
from padan.sheet import TEST_DIR

Key = tuple[str, str, str]  # (endpoint, direction, extracted path)
AGREEMENT_DIR = Path("data/labels/agreement")
SEED = 20261103
SIZES = {"mapped": 4, "ask": 1, "none": 8}  # 13 of Viator's 64 fields, in proportion to the gold


def gold_targets(spec_id: str) -> dict[Key, str]:
    """Each scoped field's gold target: a canonical path (filters as []), NONE or ASK_PARTNER."""
    found: dict[Key, str] = {}
    for entry in load_labels(TEST_DIR / f"{spec_id}.yaml"):
        target = entry.target if entry.target in (NONE, ASK_PARTNER) else normalise(entry.target)
        for path in entry.source.paths:
            found.setdefault(
                (entry.source.endpoint, entry.source.direction, normalise(path)), target
            )
    return found


def stratum(target: str) -> str:
    """Which part of the gold a field comes from: mapped, ask or none."""
    if target == NONE:
        return "none"
    if target == ASK_PARTNER:
        return "ask"
    return "mapped"


def draw(gold: dict[Key, str], sizes: dict[str, int], seed: int) -> list[Key]:
    """The same sample every time: `sizes[s]` fields per stratum, from one seeded generator."""
    rng = random.Random(seed)
    chosen: list[Key] = []
    for name, size in sizes.items():
        members = sorted(key for key, target in gold.items() if stratum(target) == name)
        chosen += rng.sample(members, size)
    return chosen


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for (gold, theirs) label pairs; None when chance agreement is total."""
    n = len(pairs)
    observed = sum(1 for a, b in pairs if a == b) / n
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    expected = sum(first[label] * second[label] for label in first) / (n * n)
    if expected == 1:
        return None
    return (observed - expected) / (1 - expected)


def their_targets(path: Path) -> dict[Key, str]:
    """The second labeller's filled sheet: one target per field, read like the gold."""
    found: dict[Key, str] = {}
    for entry in yaml.safe_load(path.read_text()):
        source = entry["source"]
        target = str(entry.get("target") or "").strip()
        target = target if target in (NONE, ASK_PARTNER) else normalise(target)
        found[(source["endpoint"], source["direction"], normalise(source["paths"][0]))] = target
    return found


def score(gold: dict[Key, str], sample: list[Key], theirs: dict[Key, str]) -> dict[str, Any]:
    """Raw agreement and kappa, overall and per stratum; every sampled field must be labelled."""
    missing = [key for key in sample if not theirs.get(key)]
    if missing:
        raise ValueError(f"{len(missing)} sampled field(s) have no target, e.g. {missing[0][2]}")
    pairs = [(gold[key], theirs[key]) for key in sample]
    report: dict[str, Any] = {
        "fields": len(pairs),
        "agree": sum(1 for a, b in pairs if a == b),
        "kappa": kappa(pairs),
        "by_stratum": {},
        "disagreements": [
            {"path": key[2], "gold": gold[key], "theirs": theirs[key]}
            for key in sample
            if gold[key] != theirs[key]
        ],
    }
    for name in SIZES:
        part = [(a, b) for a, b in pairs if stratum(a) == name]
        report["by_stratum"][name] = f"{sum(1 for a, b in part if a == b)}/{len(part)}"
    return report


def main(argv: list[str]) -> int:
    """`sample SPEC` | `score SPEC FILE`."""
    command, *rest = argv or [""]
    if command == "sample" and len(rest) == 1:
        spec_id = rest[0]
        gold = gold_targets(spec_id)
        chosen = draw(gold, SIZES, SEED)
        record = AGREEMENT_DIR / f"{spec_id}.sample.json"
        if record.exists():
            print(f"{record} exists; the sample is drawn once")
            return 1
        AGREEMENT_DIR.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps({"seed": SEED, "sizes": SIZES, "fields": chosen}, indent=1) + "\n"
        )
        fields = [
            f
            for f in scoped_fields(load_scoped(spec_id))
            if (f.endpoint, f.direction, f.path) in chosen
        ]
        sheet = AGREEMENT_DIR / f"{spec_id}.second-labeller.yaml"
        sheet.write_text(write_scaffold(spec_id, fields))
        targets = (
            AGREEMENT_DIR / "targets.md"
        )  # every canonical target, as Claude's prompt lists them
        targets.write_text("# Canonical targets\n\n" + schema_table() + "\n")
        print(f"drew {len(chosen)} fields; wrote {record}, the blank sheet {sheet} and {targets}")
        return 0
    if command == "score" and len(rest) == 2:
        spec_id, filled = rest
        record = json.loads((AGREEMENT_DIR / f"{spec_id}.sample.json").read_text())
        sample = [tuple(key) for key in record["fields"]]
        print(
            json.dumps(score(gold_targets(spec_id), sample, their_targets(Path(filled))), indent=1)
        )
        return 0
    print("usage: python -m padan.agreement sample SPEC | score SPEC FILE")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
