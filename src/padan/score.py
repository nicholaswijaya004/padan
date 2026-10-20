"""Score predicted labels against gold labels: mapping, escalation, transforms, critical errors.

The unit is a Pair, one (source field -> target) decision. Decisions S1-S7 (Day 6 journal):
- NONE is not a positive class: gold canonical + predicted NONE is a miss (FN), the reverse an FP.
- Gold ASK_PARTNER but a predicted mapping: mapping FP, escalation FN, and a critical error if
  the candidate is critical (S1).
- Gold canonical but predicted ASK_PARTNER: mapping FN, escalation FP, no critical error (S2).
- Paths match exactly, filters included; only [0] and [] are the same (S3).
- A field missing from the prediction counts as NONE.
"""

import re
from dataclasses import dataclass, field

from pydantic import BaseModel

from padan.labels import ASK_PARTNER, NONE, LabelEntry, _unwrap, normalise
from padan.schema import Booking
from padan.transforms import parse_transform

FIRST_ITEM = re.compile(r"\[0\]")


@dataclass(frozen=True, order=True)
class Pair:
    endpoint: str
    direction: str
    path: str  # source paths, joined with " + " when a label has several
    target: str


def pairs(entries: list[LabelEntry]) -> dict[Pair, LabelEntry]:
    """One Pair per label entry, with [0] read as []."""
    return {
        Pair(
            entry.source.endpoint,
            entry.source.direction,
            " + ".join(FIRST_ITEM.sub("[]", path) for path in entry.source.paths),
            entry.target,
        ): entry
        for entry in entries
    }


def critical_paths(model: type[BaseModel], prefix: str = "", inherited: bool = False) -> set[str]:
    """Target paths marked critical, or inside a critical field (total_price.currency)."""
    paths: set[str] = set()
    for name, info in model.model_fields.items():
        extra = info.json_schema_extra if isinstance(info.json_schema_extra, dict) else {}
        critical = inherited or bool(extra.get("critical"))
        path = f"{prefix}{name}"
        annotation = _unwrap(info.annotation)
        if getattr(annotation, "__origin__", None) is list:
            path += "[]"
            (annotation,) = annotation.__args__
        if critical:
            paths.add(path)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            paths |= critical_paths(annotation, f"{path}.", critical)
    return paths


CRITICAL = frozenset(critical_paths(Booking))


def is_critical(entry: LabelEntry) -> bool:
    """For ASK_PARTNER, the candidate decides (S1)."""
    target = entry.candidate if entry.target == ASK_PARTNER else entry.target
    return target is not None and normalise(target) in CRITICAL


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float | None:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else None

    @property
    def recall(self) -> float | None:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if p + r else 0.0


@dataclass
class SpecScore:
    mapping: Counts = field(default_factory=Counts)
    escalation: Counts = field(default_factory=Counts)
    transforms_right: int = 0
    transforms_total: int = 0
    critical_errors: list[Pair] = field(default_factory=list)
    errors: list[tuple[str, Pair]] = field(default_factory=list)  # (FP|FN|ESC_FP|ESC_FN|TRANSFORM)


def is_canonical(pair: Pair) -> bool:
    return pair.target not in (NONE, ASK_PARTNER)


def same_transform(gold: LabelEntry, pred: LabelEntry) -> bool:
    """Both kind=transform and the parsed transforms are equal."""
    if gold.kind != "transform" or pred.kind != "transform":
        return False
    assert gold.transform is not None and pred.transform is not None
    return parse_transform(gold.transform) == parse_transform(pred.transform)


def score_spec(gold: list[LabelEntry], pred: list[LabelEntry]) -> SpecScore:
    """Compare a prediction with gold for one spec."""
    gold_pairs, pred_pairs = pairs(gold), pairs(pred)
    score = SpecScore()

    # 1. mapping: canonical pairs only
    g = {pair for pair in gold_pairs if is_canonical(pair)}
    p = {pair for pair in pred_pairs if is_canonical(pair)}
    score.mapping = Counts(tp=len(g & p), fp=len(p - g), fn=len(g - p))
    score.errors += [("FP", pair) for pair in sorted(p - g)]
    score.errors += [("FN", pair) for pair in sorted(g - p)]

    # 2. escalation: the field is asked, whatever the candidate
    g_ask = {pair for pair in gold_pairs if pair.target == ASK_PARTNER}
    p_ask = {pair for pair in pred_pairs if pair.target == ASK_PARTNER}
    score.escalation = Counts(tp=len(g_ask & p_ask), fp=len(p_ask - g_ask), fn=len(g_ask - p_ask))
    score.errors += [("ESC_FP", pair) for pair in sorted(p_ask - g_ask)]
    score.errors += [("ESC_FN", pair) for pair in sorted(g_ask - p_ask)]

    # 3. transforms: right pairs where either side transforms (derived recipes are not scored)
    wrong_transform: set[Pair] = set()
    for pair in sorted(g & p):
        gold_entry, pred_entry = gold_pairs[pair], pred_pairs[pair]
        if "derived" in (gold_entry.kind, pred_entry.kind):
            continue
        if "transform" not in (gold_entry.kind, pred_entry.kind):
            continue
        score.transforms_total += 1
        if same_transform(gold_entry, pred_entry):
            score.transforms_right += 1
        else:
            wrong_transform.add(pair)
            score.errors.append(("TRANSFORM", pair))

    # 4. silent critical errors: a critical value filled wrongly, with no question asked
    wrong = (p - g) | wrong_transform
    score.critical_errors = sorted(pair for pair in wrong if is_critical(pred_pairs[pair]))

    return score
