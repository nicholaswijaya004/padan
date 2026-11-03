"""M3, step 1: a spec's labels as a mapping plan, one step per label that carries a target (ADR §6).

The plan is what the generator turns into code. It keeps every label that says something to do (a
mapping, or an `ask` that becomes a TODO) and drops `NONE`. Any label file works: the gold, the
corrected gold, or a system's predictions.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from padan.labels import ASK_PARTNER, NONE, LabelEntry, load_labels

Kind = Literal["direct", "transform", "derived", "ask"]


@dataclass(frozen=True)
class Step:
    endpoint: str
    direction: Literal["request", "response"]
    sources: tuple[str, ...]  # partner paths; several for a derived value
    target: str  # canonical path, filters kept (fulfilment[kind=voucher].value)
    kind: Kind
    detail: str | None = None  # the transform, the derived recipe or the partner question


@dataclass
class Plan:
    spec_id: str
    steps: list[Step]

    def operations(self) -> list[tuple[str, str]]:
        """Each (endpoint, direction) with at least one step, in the order they first appear."""
        return list(dict.fromkeys((step.endpoint, step.direction) for step in self.steps))

    def for_operation(self, endpoint: str, direction: str) -> list[Step]:
        return [s for s in self.steps if (s.endpoint, s.direction) == (endpoint, direction)]

    def kinds(self) -> Counter[str]:
        return Counter(step.kind for step in self.steps)


def step_of(entry: LabelEntry) -> Step | None:
    """The step a label stands for; None for NONE. An ask maps onto its candidate, as a TODO."""
    if entry.target == NONE:
        return None
    source = entry.source
    sources = tuple(source.paths)
    if entry.target == ASK_PARTNER:
        target = entry.candidate or ""
        return Step(source.endpoint, source.direction, sources, target, "ask", entry.question)
    kind = entry.kind or "direct"
    return Step(source.endpoint, source.direction, sources, entry.target, kind, entry.transform)


def plan_from_labels(spec_id: str, labels: list[LabelEntry]) -> Plan:
    steps = [step for step in (step_of(entry) for entry in labels) if step is not None]
    return Plan(spec_id, steps)


def load_plan(spec_id: str, label_file: Path) -> Plan:
    return plan_from_labels(spec_id, load_labels(label_file))
