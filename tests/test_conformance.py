"""M3 step 3: request bodies checked against the partner's own schema."""

from padan.conformance import request_problems, typed

SPEC = {
    "paths": {
        "/orders": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Order"}}
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "Order": {
                "type": "object",
                "required": ["ref", "qty"],
                "properties": {
                    "ref": {"type": "string", "maxLength": "8"},
                    "qty": {"type": "integer", "minimum": "1"},
                    "note": {"type": "string", "nullable": "true"},
                },
            }
        }
    },
}


def test_typed_restores_numbers_booleans_and_nullable() -> None:
    node = {"maxLength": "8", "minimum": "1.5", "nullable": "true", "type": "string", "enum": ["1"]}
    assert typed(node) == {
        "maxLength": 8,
        "minimum": 1.5,
        "nullable": True,
        "type": ["string", "null"],
        "enum": ["1"],
    }
    assert typed({"exclusiveMinimum": "true"}) == {}


def test_a_valid_body_has_no_problems() -> None:
    assert request_problems(SPEC, "POST /orders", {"ref": "A1", "qty": 2, "note": None}) == []


def test_problems_name_the_place_and_the_rule() -> None:
    assert request_problems(SPEC, "POST /orders", {"ref": "TOO-LONG-REF", "note": 3}) == [
        "(body): 'qty' is a required property",
        "note: 3 is not of type 'string', 'null'",
        "ref: 'TOO-LONG-REF' is too long",
    ]
