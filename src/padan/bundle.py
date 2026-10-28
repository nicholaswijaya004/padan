"""Bundle an OpenAPI spec split across files into one document our extractor can read.

Every `$ref` to another file (`../commons/fields.yaml#/Name`) is replaced by the node it points to;
refs inside a sub-file that start with `#` point into that sub-file. Refs that stay inside the root
file (`#/components/schemas/X`) are kept. A cycle (a schema that contains itself) is lifted into
`components/schemas` under a generated name, because extract.resolve() follows only that form.
Everything is read with yaml.BaseLoader, so values stay the strings the authors wrote.
"""

from pathlib import Path
from typing import Any

import yaml

Node = Any
Key = tuple[Path, str]


def pointer_get(document: Node, pointer: str) -> Node:
    """'/a/b~1c' -> document['a']['b/c'] (JSON pointer, RFC 6901); '' is the whole document."""
    node = document
    for part in [p for p in pointer.split("/") if p]:
        part = part.replace("~1", "/").replace("~0", "~")
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def bundle(root: Path, within: Path | None = None) -> Node:
    """The document at `root` with every file ref inlined. Refs may not leave `within`
    (default: the root's folder), so a spec cannot pull in files from elsewhere on disk."""
    root = root.resolve()
    within = (within or root.parent).resolve()
    files: dict[Path, Node] = {}
    lifted: dict[Key, str] = {}  # cyclic targets -> their name in components/schemas
    lifted_nodes: dict[str, Node] = {}

    def load(path: Path) -> Node:
        if not path.is_relative_to(within):
            raise ValueError(f"$ref leaves {within}: {path}")
        if path not in files:
            files[path] = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        return files[path]

    def name_for(key: Key) -> str:
        path, pointer = key
        base = f"{path.stem}_{pointer.rsplit('/', 1)[-1] or 'root'}"
        name, n = base, 2
        while name in lifted.values():
            name, n = f"{base}_{n}", n + 1
        return name

    def walk(node: Node, file: Path, stack: frozenset[Key]) -> Node:
        if isinstance(node, list):
            return [walk(item, file, stack) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" not in node:
            return {key: walk(value, file, stack) for key, value in node.items()}
        file_part, _, pointer = node["$ref"].partition("#")
        if not file_part and file == root:
            return node  # stays inside the root document: extract.resolve() handles it
        target = (file.parent / file_part).resolve() if file_part else file
        key = (target, pointer)
        if key in stack:  # a cycle: refer to a lifted copy instead of inlining forever
            if key not in lifted:
                lifted[key] = name_for(key)
            return {"$ref": f"#/components/schemas/{lifted[key]}"}
        resolved = walk(pointer_get(load(target), pointer), target, stack | {key})
        if key in lifted:
            lifted_nodes[lifted[key]] = resolved
        return resolved

    document = walk(load(root), root, frozenset())
    if lifted_nodes:
        schemas = document.setdefault("components", {}).setdefault("schemas", {})
        schemas.update(lifted_nodes)
    return document


def dump(document: Node) -> bytes:
    """YAML text of a bundled document; strings stay strings (safe_dump quotes '1.10')."""
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=1000).encode()
