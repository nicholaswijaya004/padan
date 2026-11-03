"""M3, step 4: can the labels produce a working integration? One table over every OpenAPI spec.

For each spec and each label source (the gold, and the frozen system's predictions), generate the
client and count:
- steps by kind, and the TODOs a person must still fill (derived recipes and partner questions);
- requests: the sample booking through every `to_…` function, checked against the partner's request
  schema, with the problems sorted into missing required fields, wrong types and the rest;
- responses: every example response in the spec through `from_…`, checked by `Booking`, with the
  canonical fields still missing or invalid.
"""

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from padan.conformance import SAMPLE_BOOKING, request_problems
from padan.extract import RAW_DIR, load_scoped, load_spec, scoped_fields
from padan.generate import Types, function_name, generate, todos
from padan.integration import to_booking
from padan.plan import load_plan
from padan.sheet import CORRECTED_DIR

DEV = ["headout-partner", "octo-core", "hotelbeds-activities"]  # hx-swota is HTML: no schema
TEST = ["viator-partner", "getyourguide-partner", "musement-partner"]
SYSTEM = "hybrid_general_claude-opus-5-5_v2"
OUT = Path("docs/results/m3")


class JSONLike(yaml.SafeLoader):
    """YAML read as JSON would arrive: numbers, booleans and null typed; dates left as text."""


JSONLike.yaml_implicit_resolvers = {
    first: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def label_file(spec_id: str, source: str) -> Path:
    """The gold (the corrected copy for test specs), or the frozen system's predictions."""
    if source == "gold":
        return (
            CORRECTED_DIR / f"{spec_id}.yaml"
            if spec_id in TEST
            else Path(f"data/labels/{spec_id}.yaml")
        )
    folder = Path("data/predictions/test") if spec_id in TEST else Path("data/predictions")
    return folder / SYSTEM / f"{spec_id}.yaml"


def pointer(document: Any, ref: str) -> Any:
    node = document
    for part in ref.removeprefix("#/").split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node


def examples(spec: Any, endpoint: str) -> list[Any]:
    """The example bodies of an operation's 200 JSON response: `example`, or each of `examples`."""
    method, path = endpoint.split(" ", 1)
    responses = spec["paths"][path][method.lower()].get("responses", {})
    response = responses.get("200") or responses.get(200) or {}  # the key may be quoted or not
    media = response.get("content", {}).get("application/json", {})
    if "example" in media:
        return [media["example"]]
    found = []
    for item in (media.get("examples") or {}).values():
        if "$ref" in item:
            item = pointer(spec, item["$ref"])
        found.append(item.get("value"))
    return [body for body in found if body is not None]


def kind_of(problem: str) -> str:
    """'missing' (a required field absent), 'type' (a value of the wrong type), or 'other'."""
    if "is a required property" in problem:
        return "missing"
    if "is not of type" in problem:
        return "type"
    return "other"


def field_types(spec_id: str) -> Types:
    """Each scoped field's type label, so requests can be cast to the partner's types; none for a
    spec that is not in the manifest."""
    try:
        fields = scoped_fields(load_scoped(spec_id))
    except KeyError:
        return {}
    return {(f.endpoint, f.direction, f.path): f.type for f in fields}


def measure(spec_id: str, labels: Path) -> dict[str, Any]:
    plan = load_plan(spec_id, labels)
    client: dict[str, Any] = {}
    code = generate(plan, labels.as_posix(), field_types(spec_id))
    exec(compile(code, f"client_{spec_id}", "exec"), client)
    spec = load_spec(RAW_DIR / f"{spec_id}.yaml")
    typed_spec = yaml.load((RAW_DIR / f"{spec_id}.yaml").read_text(), Loader=JSONLike)
    report: dict[str, Any] = {
        "steps": dict(plan.kinds()),
        "todos": len(todos(plan)),
        "requests": {},
        "responses": {},
    }
    for endpoint, direction in plan.operations():
        function = client[function_name(endpoint, direction)]
        if direction == "request":
            problems = request_problems(spec, endpoint, function(SAMPLE_BOOKING))
            counts = {
                kind: sum(1 for p in problems if kind_of(p) == kind)
                for kind in ("missing", "type", "other")
            }
            report["requests"][endpoint] = {
                "valid": not problems,
                "problems": counts,
                "list": problems,
            }
            continue
        results = []
        for body in examples(typed_spec, endpoint):
            try:
                _, notes = to_booking(function(body), our_booking_id="PADAN-M3")
                results.append({"valid": True, "fields": [], "notes": notes})
            except ValidationError as error:
                fields = sorted({str(e["loc"][0]) for e in error.errors() if e["loc"]})
                results.append({"valid": False, "fields": fields})
        report["responses"][endpoint] = results
    return report


def row(spec_id: str, source: str, report: dict[str, Any]) -> str:
    steps = report["steps"]
    kinds = "/".join(str(steps.get(k, 0)) for k in ("direct", "transform", "derived", "ask"))
    requests = report["requests"].values()
    valid = sum(1 for r in requests if r["valid"])
    problems = {k: sum(r["problems"][k] for r in requests) for k in ("missing", "type", "other")}
    examples_run = [e for results in report["responses"].values() for e in results]
    bookings = (
        f"{sum(1 for e in examples_run if e['valid'])}/{len(examples_run)}"
        if examples_run
        else "no example"
    )
    missing = sorted({f for e in examples_run for f in e["fields"]})
    counts = f"{problems['missing']} / {problems['type']} / {problems['other']}"
    cells = [spec_id, source, kinds, str(report["todos"]), f"{valid}/{len(requests)}", counts]
    cells += [bookings, ", ".join(missing) or "—"]
    return "| " + " | ".join(cells) + " |"


def main(argv: list[str]) -> int:
    """`python -m padan.m3`: every spec, gold and predictions; a table, and JSON in OUT."""
    OUT.mkdir(parents=True, exist_ok=True)
    columns = ["Spec", "Labels", "Steps d/t/dv/ask", "TODOs", "Requests valid"]
    columns += ["Problems missing / type / other", "Example → Booking", "Still missing"]
    print("| " + " | ".join(columns) + " |")
    print("| " + " | ".join("---" for _ in columns) + " |")
    for source in ("gold", "predicted"):
        reports = {}
        for spec_id in DEV + TEST:
            labels = label_file(spec_id, source)
            if not labels.exists():
                print(f"| {spec_id} | {source} | (no label file: {labels}) | | | | | |")
                continue
            reports[spec_id] = measure(spec_id, labels)
            print(row(spec_id, source, reports[spec_id]))
        (OUT / f"{source}.json").write_text(json.dumps(reports, indent=1, default=str) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
