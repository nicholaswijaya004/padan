"""Stage 1 extraction: the core walk on small fixture schemas, then the real gold files."""

from pathlib import Path
from typing import Any

import pytest

from padan.extract import (
    ExtractedField,
    evidence_of,
    example_at,
    extract,
    extract_pages,
    load_scoped,
    load_spec,
    properties,
    resolve,
    spec_values,
    walk,
    write_scaffold,
)
from padan.fetch import page_name
from padan.labels import load_labels, normalise

REPO_ROOT = Path(__file__).resolve().parent.parent
Schemas = dict[str, dict[str, Any]]

SCHEMAS: Schemas = {
    "Money": {
        "type": "object",
        "properties": {
            "amount": {"type": "number", "description": "Total amount."},
            "currency": {"type": "string"},
        },
    },
    "Price": {"$ref": "#/components/schemas/Money"},
    "Person": {
        "allOf": [
            {"properties": {"name": {"type": "string"}}},
            {"$ref": "#/components/schemas/Contactable"},
        ]
    },
    "Contactable": {"properties": {"email": {"type": ["string", "null"], "format": "email"}}},
    "Node": {
        "properties": {
            "id": {"type": "string"},
            "parent": {"$ref": "#/components/schemas/Node"},
        }
    },
    "LoopA": {"$ref": "#/components/schemas/LoopB"},
    "LoopB": {"$ref": "#/components/schemas/LoopA"},
}


def paths(node: dict[str, Any]) -> list[str]:
    return [path for path, _ in walk(node, SCHEMAS)]


# --- resolve -----------------------------------------------------------------------------------


def test_resolve_returns_a_node_without_ref_unchanged() -> None:
    node = {"type": "string"}
    assert resolve(node, SCHEMAS) is node


def test_resolve_follows_a_chain_of_refs() -> None:
    assert resolve({"$ref": "#/components/schemas/Price"}, SCHEMAS) is SCHEMAS["Money"]


def test_resolve_refuses_a_ref_cycle() -> None:
    with pytest.raises(ValueError):
        resolve({"$ref": "#/components/schemas/LoopA"}, SCHEMAS)


# --- properties --------------------------------------------------------------------------------


def test_properties_of_a_ref() -> None:
    assert list(properties({"$ref": "#/components/schemas/Money"}, SCHEMAS)) == [
        "amount",
        "currency",
    ]


def test_properties_merges_all_of_parts_in_order() -> None:
    assert list(properties({"$ref": "#/components/schemas/Person"}, SCHEMAS)) == ["name", "email"]


def test_properties_of_a_scalar_is_empty() -> None:
    assert properties({"type": "string"}, SCHEMAS) == {}


# --- walk --------------------------------------------------------------------------------------


def test_walk_flat_object() -> None:
    assert paths({"$ref": "#/components/schemas/Money"}) == ["amount", "currency"]


def test_walk_nested_object_uses_dots() -> None:
    node = {"properties": {"price": {"$ref": "#/components/schemas/Price"}}}
    assert paths(node) == ["price.amount", "price.currency"]


def test_walk_array_of_objects_adds_brackets() -> None:
    node = {
        "properties": {
            "guests": {"type": "array", "items": {"$ref": "#/components/schemas/Person"}}
        }
    }
    assert paths(node) == ["guests[].name", "guests[].email"]


def test_walk_array_of_scalars_is_one_leaf() -> None:
    node = {"properties": {"phones": {"type": "array", "items": {"type": "string"}}}}
    assert paths(node) == ["phones[]"]


def test_walk_nullable_array_in_openapi_3_1() -> None:
    node = {"properties": {"seats": {"type": ["array", "null"], "items": {"type": "string"}}}}
    assert paths(node) == ["seats[]"]


def test_walk_inline_objects_without_components() -> None:
    node = {
        "properties": {"contact": {"type": "object", "properties": {"email": {"type": "string"}}}}
    }
    assert paths(node) == ["contact.email"]


def test_walk_stops_at_recursion() -> None:
    assert paths({"$ref": "#/components/schemas/Node"}) == ["id", "parent.id", "parent.parent"]


def test_walk_returns_the_unresolved_leaf_schema() -> None:
    [(path, raw)] = walk(
        {"properties": {"price": {"$ref": "#/components/schemas/Money"}}},
        {"Money": {"type": "number"}},
    )
    assert (path, raw) == ("price", {"$ref": "#/components/schemas/Money"})


# --- around the walk (written by Claude) -------------------------------------------------------


def test_evidence_collapses_whitespace_and_falls_back_to_example() -> None:
    assert evidence_of({"description": "Line one.\n  Line two."}, {}) == "Line one. Line two."
    assert evidence_of({"example": "youth_1"}, {}) == "[no description; example: youth_1]"
    assert evidence_of({}, {}) == "[no description]"


def test_extract_applies_scope_and_exclusions() -> None:
    spec = {
        "paths": {
            "/bookings": {
                "post": {
                    "requestBody": {
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Money"}}
                        }
                    }
                }
            }
        },
        "components": {"schemas": SCHEMAS},
    }
    fields = extract(spec, ["POST /bookings request"], exclude=["currency"])
    assert fields == [
        ExtractedField(
            endpoint="POST /bookings",
            direction="request",
            path="amount",
            type="number",
            evidence="Total amount.",
        )
    ]


def test_scaffold_quotes_and_leaves_target_blank() -> None:
    field = ExtractedField(
        endpoint="GET /b",
        direction="response",
        path="ref",
        type="string",
        evidence="Supplier's ref.",
    )
    text = write_scaffold("demo", [field])
    assert "evidence: 'Supplier''s ref.'" in text
    assert "target: ''" in text


# --- example bodies (Hotelbeds: no descriptions, one example per operation) -------------------

BODY = {
    "holder": {"name": "Ana", "zipCode": "07198", "telephones": ["123", "456"]},
    "activities": [{"from": "2016-07-01", "paxes": [{"type": "ADULT"}, {"type": "CHILD"}]}],
}


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("holder.zipCode", "07198"),
        ("holder.telephones[]", "123"),
        ("activities[].paxes[].type", "ADULT"),
        ("holder.fax", None),
        ("holder.name[]", None),
    ],
)
def test_example_at(path: str, expected: Any) -> None:
    assert example_at(BODY, path) == expected


def test_example_at_without_a_body() -> None:
    assert example_at(None, "holder.name") is None


def test_evidence_prefers_description_then_field_example_then_body() -> None:
    assert evidence_of({"description": "Zip."}, {}, "07198") == "Zip."
    assert evidence_of({"example": "1"}, {}, "07198") == "[no description; example: 1]"
    assert evidence_of({}, {}, "07198") == "[no description; example: 07198]"


def test_extract_takes_evidence_from_the_operation_example() -> None:
    spec = {
        "paths": {
            "/bookings": {
                "put": {
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "properties": {"holder": {"properties": {"zipCode": {}}}}
                                },
                                "example": BODY,
                            }
                        }
                    }
                }
            }
        }
    }
    [field] = extract(spec, ["PUT /bookings request"], [])
    assert field.evidence == "[no description; example: 07198]"


def test_extract_keeps_the_enum_of_a_leaf_and_of_an_array_of_scalars() -> None:
    spec = {
        "paths": {
            "/bookings": {
                "get": {
                    "responses": {
                        "200": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {
                                                "type": "string",
                                                "enum": ["ON_HOLD", "REJECTED"],
                                            },
                                            "methods": {
                                                "type": "array",
                                                "items": {"type": "string", "enum": ["VOUCHER"]},
                                            },
                                            "note": {"type": "string"},
                                        },
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    fields = {f.path: f.values for f in extract(spec, ["GET /bookings response"], [])}
    assert fields == {"status": ["ON_HOLD", "REJECTED"], "methods[]": ["VOUCHER"], "note": []}


def test_spec_values_is_empty_without_the_raw_spec(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("- id: nowhere\n  scope: ['GET /x response']\n")
    assert spec_values("nowhere", manifest) == {}


# --- real gold files (needs data/raw/, so skipped in CI) ---------------------------------------

SCOPED = ["headout-partner", "octo-core", "hotelbeds-activities", "hx-swota"]


def scoped_fields(spec_id: str) -> list[ExtractedField]:
    """Extract a spec's labelled scope: an OpenAPI file, or XML examples in HTML pages (urls)."""
    entry = load_scoped(spec_id, REPO_ROOT / "data" / "manifest.yaml")
    if entry.urls:
        files = [REPO_ROOT / "data" / "raw" / entry.id / page_name(url) for url in entry.urls]
    else:
        files = [REPO_ROOT / "data" / "raw" / f"{spec_id}.yaml"]
    if not all(f.exists() for f in files):
        pytest.skip(f"data/raw/ has no {spec_id} (run make fetch)")
    if entry.urls:
        return extract_pages([f.read_text() for f in files], entry.scope, entry.exclude)
    return extract(load_spec(files[0]), entry.scope, entry.exclude)


@pytest.mark.parametrize("spec_id", SCOPED)
def test_gold_labels_cover_every_extracted_field_with_the_same_evidence(spec_id: str) -> None:
    fields = scoped_fields(spec_id)
    labels = load_labels(REPO_ROOT / "data" / "labels" / f"{spec_id}.yaml")
    # A field split by filter (e.g. inputFields[id=EMAIL].value) is covered by its split entries.
    labelled = {
        (lab.source.endpoint, lab.source.direction, normalise(lab.source.paths[0])): " ".join(
            lab.evidence.split()
        )
        for lab in labels
    }
    missing = [f.path for f in fields if (f.endpoint, f.direction, f.path) not in labelled]
    assert missing == []
    changed = [f.path for f in fields if labelled[(f.endpoint, f.direction, f.path)] != f.evidence]
    assert changed == []
