"""Gold label format (ADR-001 §3) and the checks every label file must pass."""

import re
import types
from pathlib import Path
from typing import Any, Literal, Union, get_args, get_origin

import yaml
from pydantic import BaseModel, Field, TypeAdapter, field_validator, model_validator

from padan.schema import Booking

NONE = "NONE"
ASK_PARTNER = "ASK_PARTNER"

FILTER = re.compile(r"\[[^\]]*\]")


def normalise(path: str) -> str:
    """Drop list positions and filters: travellers[is_lead=true].email -> travellers[].email."""
    return FILTER.sub("[]", path)


def _unwrap(annotation: Any) -> Any:
    """X | None -> X."""
    if get_origin(annotation) in (Union, types.UnionType):
        (inner,) = [arg for arg in get_args(annotation) if arg is not type(None)]
        return inner
    return annotation


def target_paths(model: type[BaseModel], prefix: str = "") -> set[str]:
    """Every path a label may point at: leaf fields, plus lists themselves (for count())."""
    paths: set[str] = set()
    for name, field in model.model_fields.items():
        path = f"{prefix}{name}"
        annotation = _unwrap(field.annotation)
        if get_origin(annotation) is list:
            path += "[]"
            paths.add(path)
            (annotation,) = get_args(annotation)
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            paths |= target_paths(annotation, prefix=f"{path}.")
        else:
            paths.add(path)
    return paths


VALID_TARGETS = frozenset(target_paths(Booking))


class Source(BaseModel):
    endpoint: str
    direction: Literal["request", "response"]
    paths: list[str] = Field(min_length=1)


class LabelEntry(BaseModel):
    source: Source
    target: str
    kind: Literal["direct", "transform", "derived"] | None = None
    transform: str | None = None
    evidence: str = Field(min_length=1)
    candidate: str | None = None
    question: str | None = None

    @field_validator("kind", "transform", "candidate", "question", mode="before")
    @classmethod
    def empty_is_missing(cls, value: Any) -> Any:
        return None if value == "" else value

    @model_validator(mode="after")
    def follows_adr_001(self) -> "LabelEntry":
        is_canonical = self.target not in (NONE, ASK_PARTNER)
        if is_canonical and normalise(self.target) not in VALID_TARGETS:
            raise ValueError(f"target {self.target!r} is not a Booking schema path")
        if is_canonical and self.kind is None:
            raise ValueError("a canonical target needs a kind")
        if not is_canonical and self.kind is not None:
            raise ValueError(f"{self.target} takes no kind")
        if (self.kind in ("transform", "derived")) != (self.transform is not None):
            raise ValueError("transform is required for transform/derived, and only for them")
        if self.target == ASK_PARTNER and self.question is None:
            raise ValueError("ASK_PARTNER needs a question for the partner")
        if self.target != ASK_PARTNER and (self.question or self.candidate):
            raise ValueError("candidate and question are only for ASK_PARTNER")
        if self.candidate is not None and normalise(self.candidate) not in VALID_TARGETS:
            raise ValueError(f"candidate {self.candidate!r} is not a Booking schema path")
        return self


LABELS = TypeAdapter(list[LabelEntry])


def load_labels(path: Path) -> list[LabelEntry]:
    """Parse a label file; a ValidationError lists every bad entry by index."""
    entries = LABELS.validate_python(yaml.safe_load(path.read_text()))
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    for i, entry in enumerate(entries):
        key = (entry.source.endpoint, entry.source.direction, tuple(entry.source.paths))
        if key in seen:
            raise ValueError(f"entry {i}: source {key} is labelled twice")
        seen.add(key)
    return entries
