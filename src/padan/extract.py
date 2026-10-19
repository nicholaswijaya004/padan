"""Stage 1 extraction for OpenAPI specs: spec → the fields in label scope (path, type, evidence).

The core walk (`resolve`, `properties`, `walk`) turns one JSON Schema into leaf paths. The rest
picks the schemas the manifest puts in scope and renders the label scaffold.
"""

import json
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

Node = dict[str, Any]

MAX_REF_HOPS = 20


class ExtractedField(BaseModel):
    """One partner field in label scope, as written into a label's `source` and `evidence`."""

    endpoint: str
    direction: Literal["request", "response"]
    path: str
    type: str
    evidence: str


class ScopedSpec(BaseModel):
    """The manifest keys extraction needs; other keys are ignored."""

    id: str
    scope: list[str] = []
    exclude: list[str] = []


# --- core walk ---------------------------------------------------------------------------------


def resolve(node: Node, schemas: dict[str, Node]) -> Node:
    """Follow `$ref` until reaching a node without one; fail after MAX_REF_HOPS (a cycle).

    A ref looks like "#/components/schemas/Money": the schema's name is the part after the last "/".
    """
    hops = 0
    while "$ref" in node:
        if hops == MAX_REF_HOPS:
            raise ValueError(f"$ref chain longer than {MAX_REF_HOPS} at {node['$ref']}")
        name = node["$ref"].rsplit("/", 1)[-1]
        node = schemas[name]
        hops += 1
    return node


def properties(node: Node, schemas: dict[str, Node]) -> dict[str, Node]:
    """A schema's own properties plus those of its allOf / oneOf / anyOf parts, in order.

    Resolve first: the node may be a $ref. Each part of allOf/oneOf/anyOf may itself be a $ref,
    or have its own allOf, so collect their properties recursively.
    """
    node = resolve(node, schemas)
    props: dict[str, Node] = dict(node.get("properties") or {})
    for key in ("allOf", "oneOf", "anyOf"):
        for part in node.get(key) or []:
            props.update(properties(part, schemas))
    return props


def walk(
    node: Node, schemas: dict[str, Node], prefix: str = "", seen: frozenset[str] = frozenset()
) -> list[tuple[str, Node]]:
    """Every leaf path under `node`, with the leaf's unresolved schema; arrays add `[]`.

    For each property:
      - path is "prefix.name" (or just "name" at the top);
      - if its resolved type includes "array", the child is its `items` and the path gets "[]";
      - if the child has properties of its own, recurse into it with the path as the new prefix;
        otherwise it is a leaf: append (path, raw), where raw is the property's unresolved node;
      - `seen` holds the $refs already on the current branch: a child whose $ref is in `seen`
        is a leaf (recursion), and a child's $ref is added to `seen` before recursing into it.
    """
    leaves: list[tuple[str, Node]] = []
    for name, raw in properties(node, schemas).items():
        path = f"{prefix}.{name}" if prefix else f"{name}"
        resolved = resolve(raw, schemas)
        is_array = "array" in types_of(resolved)
        child = resolved.get("items", {}) if is_array else raw
        ref = child.get("$ref")
        if is_array:
            path += "[]"
        if ref in seen or not properties(child, schemas):
            leaves.append((path, raw))
            continue
        leaves += walk(child, schemas, path, seen | {ref} if ref else seen)
    return leaves


# --- around the walk ---------------------------------------------------------------------------


def types_of(node: Node) -> list[str]:
    """`type` as a list: OpenAPI 3.1 allows ["string", "null"], 3.0 a single string."""
    t = node.get("type", "")
    return t if isinstance(t, list) else [t]


def type_label(raw: Node, schemas: dict[str, Node]) -> str:
    """Human-readable type for the scaffold comment, e.g. `string|null/email`."""
    node = resolve(raw, schemas)
    kinds = [t for t in types_of(node) if t]
    label = "|".join(t for t in kinds if t != "null") + ("|null" if "null" in kinds else "")
    if not label:
        label = next((key for key in ("oneOf", "anyOf", "allOf") if node.get(key)), "")
    return label + (f"/{node['format']}" if "format" in node else "")


def evidence_of(raw: Node, schemas: dict[str, Node]) -> str:
    """The description, whitespace collapsed; the example when there is none."""
    node = resolve(raw, schemas)
    text = str(raw.get("description") or node.get("description") or "")
    if text.strip():
        return " ".join(text.split())
    example = raw.get("example", node.get("example"))
    return f"[no description; example: {example}]" if example else "[no description]"


def operation_schema(spec: Node, endpoint: str, direction: str) -> Node:
    """The JSON request body (request) or 200 response (response) schema of `METHOD /path`."""
    method, path = endpoint.split(" ", 1)
    operation = spec["paths"][path][method.lower()]
    if direction == "request":
        content = operation["requestBody"]["content"]
    else:
        content = operation["responses"]["200"]["content"]
    schema: Node = content["application/json"]["schema"]
    return schema


def extract(spec: Node, scope: list[str], exclude: list[str]) -> list[ExtractedField]:
    """All fields of the scoped operations, in spec order, minus excluded path prefixes."""
    schemas: dict[str, Node] = spec.get("components", {}).get("schemas", {})
    fields: list[ExtractedField] = []
    for item in scope:
        method, path, direction = item.split(" ")
        endpoint = f"{method} {path}"
        for leaf, raw in walk(operation_schema(spec, endpoint, direction), schemas):
            if any(leaf.startswith(prefix) for prefix in exclude):
                continue
            fields.append(
                ExtractedField(
                    endpoint=endpoint,
                    direction="request" if direction == "request" else "response",
                    path=leaf,
                    type=type_label(raw, schemas),
                    evidence=evidence_of(raw, schemas),
                )
            )
    return fields


def quote(text: str) -> str:
    """YAML single-quoted scalar."""
    return "'" + text.replace("'", "''") + "'"


def write_scaffold(spec_id: str, fields: list[ExtractedField]) -> str:
    """Render the label scaffold: source and evidence filled, target and kind blank."""
    lines = [
        f"# Label scaffold for {spec_id}, generated by padan.extract from the locked spec.",
        "# source + evidence are copied verbatim (deterministic extraction). Do not edit evidence.",
    ]
    section = ""
    for field in fields:
        heading = f"{field.endpoint} ({field.direction})"
        if heading != section:
            lines += ["", f"# ---------------- {heading}"]
            section = heading
        lines += [
            "- source:",
            f"    endpoint: {quote(field.endpoint)}",
            f"    direction: {field.direction}",
            f"    paths: [{quote(field.path)}]",
            f"  # type: {field.type}",
            "  target: ''",
            "  kind: ''",
            f"  evidence: {quote(field.evidence)}",
            "",
        ]
    return "\n".join(lines).rstrip("\n") + "\n"


MANIFEST = Path("data/manifest.yaml")
RAW_DIR = Path("data/raw")
SCAFFOLD_DIR = Path("data/scaffolds")


def load_scoped(spec_id: str, manifest: Path = MANIFEST) -> ScopedSpec:
    """The manifest entry for `spec_id`, with its label scope."""
    for entry in yaml.safe_load(manifest.read_text()):
        if entry["id"] == spec_id:
            return ScopedSpec.model_validate(entry)
    raise KeyError(f"{spec_id} is not in {manifest}")


def load_spec(path: Path) -> Node:
    """Parse a spec keeping every scalar a string (BaseLoader: no dates, no Norway problem)."""
    spec: Node = yaml.load(path.read_bytes(), Loader=yaml.BaseLoader)
    return spec


def main(argv: list[str]) -> int:
    """`python -m padan.extract SPEC_ID`: write data/scaffolds/SPEC_ID.yaml (not committed)."""
    if len(argv) != 1:
        print("usage: python -m padan.extract SPEC_ID")
        return 2
    entry = load_scoped(argv[0])
    if not entry.scope:
        print(f"{entry.id}: no scope in the manifest")
        return 1
    fields = extract(load_spec(RAW_DIR / f"{entry.id}.yaml"), entry.scope, entry.exclude)
    SCAFFOLD_DIR.mkdir(parents=True, exist_ok=True)
    out = SCAFFOLD_DIR / f"{entry.id}.yaml"
    out.write_text(write_scaffold(entry.id, fields))
    print(json.dumps({"spec": entry.id, "fields": len(fields), "scaffold": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
