"""Stage 1 extraction for OpenAPI specs: spec → the fields in label scope (path, type, evidence).

The core walk (`resolve`, `properties`, `walk`) turns one JSON Schema into leaf paths. The rest
picks the schemas the manifest puts in scope and renders the label scaffold.
"""

import html
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from padan.fetch import page_name

Node = dict[str, Any]

MAX_REF_HOPS = 20


class ExtractedField(BaseModel):
    """One partner field in label scope, as written into a label's `source` and `evidence`."""

    endpoint: str
    direction: Literal["request", "response"]
    path: str
    type: str
    evidence: str
    values: list[str] = []  # the schema's `enum`, when it lists the allowed values


class ScopedSpec(BaseModel):
    """The manifest keys extraction needs; other keys are ignored."""

    id: str
    urls: list[str] = []
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
        path = f"{prefix}.{name}" if prefix else name
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


def enum_of(raw: Node, schemas: dict[str, Node]) -> list[str]:
    """The `enum` a leaf lists (for an array of scalars, its items'), as strings; else []."""
    node = resolve(raw, schemas)
    if "array" in types_of(node):
        node = resolve(node.get("items", {}), schemas)
    return [str(value) for value in node.get("enum", []) if value is not None]


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


def example_at(example: Any, path: str) -> Any:
    """The value at `path` in an example body; for `name[]`, the first element. None if absent.
    A path starting with `[].` is in a body that is itself a list."""
    value = example
    for part in path.split("."):
        is_list = part.endswith("[]")
        name = part[:-2] if is_list else part
        if name:
            if not isinstance(value, dict) or name not in value:
                return None
            value = value[name]
        if is_list:
            if not isinstance(value, list) or not value:
                return None
            value = value[0]
    return value


def evidence_of(raw: Node, schemas: dict[str, Node], body_example: Any = None) -> str:
    """The description, whitespace collapsed; else the field's own example; else its value in the
    operation's example body (`body_example`, already looked up at this field's path)."""
    node = resolve(raw, schemas)
    text = str(raw.get("description") or node.get("description") or "")
    if text.strip():
        return " ".join(text.split())
    example = raw.get("example", node.get("example"))
    if example is None:
        example = body_example
    return f"[no description; example: {example}]" if example is not None else "[no description]"


def operation_content(spec: Node, endpoint: str, direction: str) -> Node:
    """The JSON media object (schema + example) of a request body or a 200 response."""
    method, path = endpoint.split(" ", 1)
    operation = spec["paths"][path][method.lower()]
    if direction == "request":
        content = operation["requestBody"]["content"]
    else:
        content = operation["responses"]["200"]["content"]
    media: Node = content["application/json"]
    return media


def extract(spec: Node, scope: list[str], exclude: list[str]) -> list[ExtractedField]:
    """All fields of the scoped operations, in spec order, minus excluded path prefixes."""
    schemas: dict[str, Node] = spec.get("components", {}).get("schemas", {})
    fields: list[ExtractedField] = []
    for item in scope:
        method, path, direction = item.split(" ")
        endpoint = f"{method} {path}"
        media = operation_content(spec, endpoint, direction)
        schema, prefix = media["schema"], ""
        if "array" in types_of(resolve(schema, schemas)):  # a list at the top: paths start "[]."
            schema, prefix = resolve(schema, schemas).get("items", {}), "[]"
        for leaf, raw in walk(schema, schemas, prefix):
            if any(leaf.startswith(prefix) for prefix in exclude):
                continue
            fields.append(
                ExtractedField(
                    endpoint=endpoint,
                    direction="request" if direction == "request" else "response",
                    path=leaf,
                    type=type_label(raw, schemas),
                    evidence=evidence_of(raw, schemas, example_at(media.get("example"), leaf)),
                    values=enum_of(raw, schemas),
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


# --- XML examples in HTML pages (e.g. HX / OpenTravel) -----------------------------------------


@dataclass
class XmlElement:
    """A parsed XML element: namespace prefixes dropped, xmlns attributes ignored."""

    name: str
    attrs: dict[str, str]
    children: list["XmlElement"] = dataclass_field(default_factory=list)
    text: str = ""


@dataclass
class XmlBlock:
    """One XML example on a page, with the endpoint named by the nearest `POST https://...` line."""

    endpoint: str | None
    root: XmlElement


CODE_BLOCK = re.compile(r"<code([^>]*)>(.*?)</code>", re.S)
REQUEST_LINE = re.compile(r"(GET|POST|PUT|PATCH|DELETE)\s+https?://[^/\s]+(\S+)")
XML_TOKEN = re.compile(
    r"<(/?)([A-Za-z_][\w:.-]*)((?:\s+[\w:.-]+\s*=\s*\"[^\"]*\")*)\s*(/?)>|([^<]+)"
)
XML_ATTR = re.compile(r"([\w:.-]+)\s*=\s*\"([^\"]*)\"")
PLACEHOLDER = "[.."


def local_name(name: str) -> str:
    """`vx:ReservationID` → `ReservationID`."""
    return name.rsplit(":", 1)[-1]


def parse_xml(text: str) -> XmlElement:
    """Parse an XML example tolerantly and return its root element.

    Documentation examples are not always well-formed: a `[..]` placeholder can swallow a closing
    tag. Repair rule: when an element closes, any child still open inside it closes too.
    """
    top = XmlElement("#document", {})
    stack = [top]
    for match in XML_TOKEN.finditer(text):
        closing, name, attrs, self_closing, chars = match.groups()
        if chars is not None:
            stack[-1].text += chars
            continue
        name = local_name(name)
        if closing:
            if any(open_el.name == name for open_el in stack[1:]):
                while stack[-1].name != name:
                    stack.pop()
                stack.pop()
            continue
        element = XmlElement(
            name, {k: v for k, v in XML_ATTR.findall(attrs) if not k.startswith("xmlns")}
        )
        stack[-1].children.append(element)
        if not self_closing:
            stack.append(element)
    if len(top.children) != 1:
        raise ValueError(f"expected one root element, found {len(top.children)}")
    return top.children[0]


def xml_blocks(page: str) -> list[XmlBlock]:
    """Every `lang-xml` code block on an HTML page, in order."""
    endpoint = None
    blocks: list[XmlBlock] = []
    for match in CODE_BLOCK.finditer(page):
        text = html.unescape(match.group(2)).strip()
        request = REQUEST_LINE.match(text)
        if request:
            endpoint = f"{request.group(1)} {request.group(2)}"
        elif "lang-xml" in match.group(1) and text.startswith("<"):
            blocks.append(XmlBlock(endpoint, parse_xml(text)))
    return blocks


def xml_leaves(element: XmlElement, prefix: str = "") -> list[tuple[str, str]]:
    """Every attribute (`path@Name`) and leaf text (`path`) under `element`, with its value.

    Repeated child names add `[]`; a path seen twice keeps its first value; placeholder text
    (starting with "[..") is skipped.
    """
    rows = [(f"{prefix}@{name}", value) for name, value in element.attrs.items()]
    text = element.text.strip()
    if text and not element.children and not text.startswith(PLACEHOLDER):
        rows.append((prefix, text))
    counts = Counter(child.name for child in element.children)
    seen: set[str] = set()
    for child in element.children:
        path = f"{prefix}.{child.name}" if prefix else child.name
        if counts[child.name] > 1:
            path += "[]"
        for row in xml_leaves(child, path):
            if row[0] not in seen:
                rows.append(row)
                seen.add(row[0])
    return rows


def extract_pages(pages: list[str], scope: list[str], exclude: list[str]) -> list[ExtractedField]:
    """Fields of the XML examples whose root the scope names, e.g. "OTA_CruiseBookRS response"."""
    blocks = [block for page in pages for block in xml_blocks(page)]
    fields: list[ExtractedField] = []
    for item in scope:
        root_name, direction = item.split(" ")
        matches = [block for block in blocks if block.root.name == root_name]
        if len(matches) != 1:
            raise ValueError(f"{root_name}: expected one example, found {len(matches)}")
        block = matches[0]
        endpoint = block.endpoint or root_name
        for path, value in xml_leaves(block.root):
            if any(path.startswith(prefix) for prefix in exclude):
                continue
            fields.append(
                ExtractedField(
                    endpoint=endpoint,
                    direction="request" if direction == "request" else "response",
                    path=path,
                    type="xml attribute" if "@" in path else "xml text",
                    evidence=f"[no description; example: {value}]",
                )
            )
    return fields


MANIFEST = Path("data/manifest.yaml")
RAW_DIR = Path("data/raw")
SCAFFOLD_DIR = Path("data/scaffolds")


def load_scoped(spec_id: str, manifest: Path = MANIFEST) -> ScopedSpec:
    """The manifest entry for `spec_id`, with its label scope."""
    for entry in yaml.safe_load(manifest.read_text()):
        if entry["id"] == spec_id:
            return ScopedSpec.model_validate(entry)
    raise KeyError(f"{spec_id} is not in {manifest}")


def spec_values(spec_id: str, manifest: Path = MANIFEST) -> dict[tuple[str, str, str], list[str]]:
    """Allowed values per field (endpoint, direction, path), read from data/raw/ at run time.

    Empty when the spec is not fetched or is not an OpenAPI file. Partner specs are never committed,
    so these lists exist only on the machine that fetched them.
    """
    entry = load_scoped(spec_id, manifest)
    raw = RAW_DIR / f"{spec_id}.yaml"
    if entry.urls or not entry.scope or not raw.exists():
        return {}
    return {
        (f.endpoint, f.direction, f.path): f.values
        for f in extract(load_spec(raw), entry.scope, entry.exclude)
        if f.values
    }


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
    if entry.urls:
        pages = [(RAW_DIR / entry.id / page_name(url)).read_text() for url in entry.urls]
        fields = extract_pages(pages, entry.scope, entry.exclude)
    else:
        fields = extract(load_spec(RAW_DIR / f"{entry.id}.yaml"), entry.scope, entry.exclude)
    SCAFFOLD_DIR.mkdir(parents=True, exist_ok=True)
    out = SCAFFOLD_DIR / f"{entry.id}.yaml"
    out.write_text(write_scaffold(entry.id, fields))
    print(json.dumps({"spec": entry.id, "fields": len(fields), "scaffold": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
