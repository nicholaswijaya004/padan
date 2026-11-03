"""M3, step 3: does a generated client produce what the partner accepts? (requests, Day 21)

`to_…` functions are run on one sample booking, and each request body is checked against the
partner's own request schema from the spec, with the jsonschema library. A body the partner's schema
rejects is counted, with every problem named.

Specs are read the way padan always reads them (yaml.BaseLoader: every scalar a string), so before
validating, the keywords that must be numbers or booleans are turned back into them, and OpenAPI
3.0's `nullable: true` becomes a JSON Schema `null` type.
"""

import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from padan.extract import RAW_DIR, load_spec, operation_content
from padan.generate import function_name, generate
from padan.plan import load_plan

Node = Any
NUMBERS = {
    "minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties",
    "minimum", "maximum", "multipleOf",
}  # fmt: skip
BOOLEANS = {"nullable", "uniqueItems", "readOnly", "writeOnly", "deprecated"}

SAMPLE_BOOKING: dict[str, Any] = {
    "our_booking_id": "PADAN-2026-0001",
    "status": "confirmed",
    "contact": {
        "given_name": "Ana",
        "family_name": "Lima",
        "email": "ana.lima@example.com",
        "phones": ["+6281234567890"],
    },
    "travellers": [
        {"given_name": "Ana", "family_name": "Lima", "is_lead": True, "traveller_type": "adult"},
        {"given_name": "Ben", "family_name": "Lima", "is_lead": False, "traveller_type": "child"},
    ],
    "total_price": {"amount": "120.50", "currency": "EUR"},
    "items": [
        {
            "product_id": "1001",  # catalogue IDs as many partners issue them: digits, kept as text
            "option_id": "2002",
            "start_date": "2026-12-01",
            "start_time": "09:30:00",
            "activity": {"slot_id": "SLOT-1", "service_language": "en"},
        }
    ],
}


def number(text: str) -> int | float:
    return float(text) if any(c in text for c in ".eE") else int(text)


def typed(node: Node) -> Node:
    """A schema read as strings, with numbers, booleans and OpenAPI 3.0 `nullable` restored."""
    if isinstance(node, list):
        return [typed(item) for item in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    for key, value in node.items():
        if key in NUMBERS and isinstance(value, str):
            out[key] = number(value)
        elif key in BOOLEANS and isinstance(value, str):
            out[key] = value == "true"
        elif key in ("exclusiveMinimum", "exclusiveMaximum") and value in ("true", "false"):
            continue  # OpenAPI 3.0's boolean form; JSON Schema 2020-12 wants a number
        elif key == "additionalProperties" and value in ("true", "false"):
            out[key] = value == "true"
        elif key in ("example", "examples", "default", "enum"):
            out[key] = value  # data, not schema: leave as written
        else:
            out[key] = typed(value)
    if out.get("nullable") is True and isinstance(out.get("type"), str):
        out["type"] = [out["type"], "null"]
    return out


def request_problems(spec: Node, endpoint: str, body: Any) -> list[str]:
    """Everything the partner's request schema says is wrong with `body`; empty means valid."""
    schema = operation_content(spec, endpoint, "request")["schema"]
    root = typed({"components": spec.get("components", {}), **schema})
    errors = Draft202012Validator(root).iter_errors(body)
    found = [f"{'/'.join(map(str, e.absolute_path)) or '(body)'}: {e.message}" for e in errors]
    return sorted(found)


def check_requests(spec_id: str, label_file: Path, booking: dict[str, Any]) -> dict[str, Any]:
    """Generate the client from `label_file`, build every request from `booking`, validate each."""
    plan = load_plan(spec_id, label_file)
    client: dict[str, Any] = {}
    exec(compile(generate(plan, label_file.as_posix()), f"client_{spec_id}", "exec"), client)
    spec = load_spec(RAW_DIR / f"{spec_id}.yaml")
    report: dict[str, Any] = {}
    for endpoint, direction in plan.operations():
        if direction != "request":
            continue
        body = client[function_name(endpoint, direction)](booking)
        report[endpoint] = {"body": body, "problems": request_problems(spec, endpoint, body)}
    return report


def main(argv: list[str]) -> int:
    """`python -m padan.conformance SPEC LABEL_FILE`: request bodies from the sample booking."""
    if len(argv) != 2:
        print("usage: python -m padan.conformance SPEC LABEL_FILE")
        return 2
    report = check_requests(argv[0], Path(argv[1]), SAMPLE_BOOKING)
    for endpoint, result in report.items():
        verdict = "valid" if not result["problems"] else f"{len(result['problems'])} problem(s)"
        print(f"\n== {endpoint} request: {verdict}")
        print(json.dumps(result["body"], indent=1, default=str))
        for problem in result["problems"]:
            print(f"  - {problem}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
