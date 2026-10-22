"""Candidate finder: which canonical targets could a partner field be? (Day 8, ADR-001 E1-E5)

A field is split into its leaf name and its parents. The leaf's tokens must equal a lexicon
entry's tokens exactly (C1). The parents become an entity path, e.g. unitItems[].contact ->
(ticket, contact), read as the context key "ticket contact"; an entry lists the context keys
it accepts and must name one exactly, so a ticket's contact never falls back to the booking
contact (C2).
Entries are data in data/rules/lexicon.yaml, each with the dev specs it was learnt from (C3), which
is what lets leave-one-spec-out switch off a spec's own entries (E1).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from padan.labels import VALID_TARGETS, normalise
from padan.tokens import tokens

LEXICON = Path("data/rules/lexicon.yaml")
FILTER = re.compile(r"\[[^\]]*\]")
WORD = re.compile(r"[a-z0-9]+")


class Entry(BaseModel):
    id: str
    targets: list[str] = Field(min_length=1)  # several only for a split, e.g. date + time
    leaf: list[list[str]] = Field(min_length=1)  # token sets that mean this; exact match
    context: list[str] = Field(min_length=1)  # context keys; "" is the booking root
    learnt_from: list[str] = Field(min_length=1)
    escalate: bool = False  # learnt from an ASK_PARTNER label: the meaning was not documented

    @field_validator("targets")
    @classmethod
    def targets_exist(cls, targets: list[str]) -> list[str]:
        unknown = [t for t in targets if normalise(t) not in VALID_TARGETS]
        if unknown:
            raise ValueError(f"not Booking schema paths: {unknown}")
        return targets

    @field_validator("leaf")
    @classmethod
    def leaf_is_words(cls, leaf: list[list[str]]) -> list[list[str]]:
        # E1 rule shape: entries hold lowercase words, never a partner path
        for words in leaf:
            if not words or not all(WORD.fullmatch(w) for w in words):
                raise ValueError(f"leaf {words} must be lowercase words")
        return leaf


class Lexicon(BaseModel):
    entities: dict[str, list[str]]  # entity -> parent words that signal it; order is priority
    wrappers: list[str]  # parent words that carry no meaning (info, details...)
    dependents: list[str]  # entities read together with their owner (ticket contact)
    entries: list[Entry]


def load_lexicon(path: Path = LEXICON) -> Lexicon:
    return Lexicon.model_validate(yaml.safe_load(path.read_text()))


def split(path: str) -> tuple[str, list[str]]:
    """'a[].b.c@D' -> ('D', ['a', 'b', 'c']); filters and list markers are dropped."""
    segments = FILTER.sub("", path).split(".")
    *parents, last = segments
    if "@" in last:
        owner, _, leaf = last.partition("@")
        parents += [owner] if owner else []
        return leaf, parents
    return last, parents


def entity_path(parents: list[str], lexicon: Lexicon) -> tuple[str, ...]:
    """Parents -> entities, root first; wrappers skipped, repeats merged, unknown -> 'other'."""
    path: list[str] = []
    for segment in parents:
        words = set(tokens(segment))
        entity = next((e for e, signals in lexicon.entities.items() if words & set(signals)), None)
        if entity is None:
            if words <= set(lexicon.wrappers):
                continue
            entity = "other"
        if not path or path[-1] != entity:
            path.append(entity)
    return tuple(path)


def context_key(path: tuple[str, ...], lexicon: Lexicon) -> str:
    """The last entity, plus its owner if it is a dependent; the booking counts as the root."""
    path = tuple(entity for entity in path if entity != "booking")
    if not path:
        return ""
    if path[-1] in lexicon.dependents and len(path) > 1:
        return f"{path[-2]} {path[-1]}"
    return path[-1]


@dataclass(frozen=True)
class Candidate:
    targets: tuple[str, ...]
    entry: str
    escalate: bool = False


def candidates(path: str, lexicon: Lexicon, held_out: str | None = None) -> list[Candidate]:
    """Every entry whose leaf words and context key both match exactly.

    held_out: a spec id whose own entries are switched off (leave-one-spec-out).
    """
    leaf, parents = split(path)
    leaf_words = sorted(tokens(leaf))
    key = context_key(entity_path(parents, lexicon), lexicon)
    return [
        Candidate(tuple(entry.targets), entry.id, entry.escalate)
        for entry in lexicon.entries
        if (held_out is None or set(entry.learnt_from) - {held_out})
        and key in entry.context
        and leaf_words in [sorted(words) for words in entry.leaf]
    ]
