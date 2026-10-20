"""Score a directory of prediction files against the gold labels (S4, S7).

    python -m padan.report PRED_DIR [JSON_OUT]

Prints a markdown table: one row per spec (micro within the spec), then the macro average across
specs (the headline) and the micro total. JSON_OUT gets every count and the per-pair error list.
"""

import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

from padan.baselines import LABEL_DIR, gold_files
from padan.labels import load_labels
from padan.score import Counts, SpecScore, score_spec


def score_dir(pred_dir: Path, label_dir: Path = LABEL_DIR) -> dict[str, SpecScore]:
    """Every spec with a gold file; a missing prediction file scores as all NONE."""
    scores = {}
    for gold_path in gold_files(label_dir):
        pred_path = pred_dir / gold_path.name
        pred = load_labels(pred_path) if pred_path.exists() else []
        scores[gold_path.stem] = score_spec(load_labels(gold_path), pred)
    return scores


def macro(values: list[float | None]) -> float | None:
    """Mean over the specs where the metric is defined."""
    defined = [v for v in values if v is not None]
    return mean(defined) if defined else None


def total(counts: list[Counts]) -> Counts:
    return Counts(
        tp=sum(c.tp for c in counts), fp=sum(c.fp for c in counts), fn=sum(c.fn for c in counts)
    )


def fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def transform_rate(score: SpecScore) -> float | None:
    return score.transforms_right / score.transforms_total if score.transforms_total else None


def table(scores: dict[str, SpecScore]) -> str:
    rows = [
        "| Spec | Map P | Map R | Map F1 | Esc P | Esc R | Transforms | Critical errors |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for spec, s in scores.items():
        m, e = s.mapping, s.escalation
        rows.append(
            f"| {spec} | {fmt(m.precision)} | {fmt(m.recall)} | {fmt(m.f1)} | "
            f"{fmt(e.precision)} | {fmt(e.recall)} | {s.transforms_right}/{s.transforms_total} | "
            f"{len(s.critical_errors)} |"
        )
    all_ = list(scores.values())
    rows.append(
        "| **macro (headline)** | "
        + " | ".join(
            fmt(macro([metric(s) for s in all_]))
            for metric in (
                lambda s: s.mapping.precision,
                lambda s: s.mapping.recall,
                lambda s: s.mapping.f1,
                lambda s: s.escalation.precision,
                lambda s: s.escalation.recall,
                transform_rate,
            )
        )
        + f" | {sum(len(s.critical_errors) for s in all_)} |"
    )
    m, e = total([s.mapping for s in all_]), total([s.escalation for s in all_])
    right, n = sum(s.transforms_right for s in all_), sum(s.transforms_total for s in all_)
    rows.append(
        f"| micro (all pairs) | {fmt(m.precision)} | {fmt(m.recall)} | {fmt(m.f1)} | "
        f"{fmt(e.precision)} | {fmt(e.recall)} | {right}/{n} | "
        f"{sum(len(s.critical_errors) for s in all_)} |"
    )
    return "\n".join(rows)


def as_json(scores: dict[str, SpecScore]) -> dict[str, Any]:
    def counts(c: Counts) -> dict[str, Any]:
        return {"tp": c.tp, "fp": c.fp, "fn": c.fn, "p": c.precision, "r": c.recall, "f1": c.f1}

    return {
        spec: {
            "mapping": counts(s.mapping),
            "escalation": counts(s.escalation),
            "transforms": {"right": s.transforms_right, "total": s.transforms_total},
            "critical_errors": [vars(pair) for pair in s.critical_errors],
            "errors": [{"kind": kind, **vars(pair)} for kind, pair in s.errors],
        }
        for spec, s in scores.items()
    }


def main(argv: list[str]) -> int:
    if len(argv) not in (1, 2):
        print("usage: python -m padan.report PRED_DIR [JSON_OUT]")
        return 2
    scores = score_dir(Path(argv[0]))
    print(table(scores))
    if len(argv) == 2:
        Path(argv[1]).write_text(json.dumps(as_json(scores), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
