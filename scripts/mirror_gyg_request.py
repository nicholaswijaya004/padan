"""Mirror my own frozen GET-response labels onto GetYourGuide's create-request fields (no model).

A request field gets a proposed pick when, with `data.` dropped from the front and
`.participant_answers` dropped from the middle, its path is a response field I already picked.
Asks are not mirrored (an ask is about what the response says). Prints YAML picks per row; with
`--write SHEET` it inserts them under their rows in SHEET instead (comments kept), for review there.
"""

import sys
from pathlib import Path
from typing import Any

import yaml

from padan.extract import load_scoped, scoped_fields
from padan.sheet import ROWS, Pick

GET, REQ = "GET /{version}/bookings/{booking_hash}", "POST /{version}/bookings"


def as_response(path: str) -> str:
    return path.removeprefix("data.").replace(".participant_answers.", ".")


def pick_text(pick: dict[str, Any]) -> str:
    source = pick["source"]
    paths = ", ".join(f"'{p}'" for p in source["paths"])
    lines = [
        f"    - source: {{endpoint: '{source['endpoint']}', direction: request, paths: [{paths}]}}",
        f"      kind: {pick['kind']}",
    ]
    lines += [f"      {key}: '{pick[key]}'" for key in ("target", "transform") if key in pick]
    return "\n".join(lines)


sheet = Path(sys.argv[1])
rows = ROWS.validate_python(yaml.safe_load(sheet.read_text()))
request = [f.path for f in scoped_fields(load_scoped("getyourguide-partner")) if f.endpoint == REQ]
by_response: dict[tuple[str, ...], list[tuple[str, Pick]]] = {}
for row in rows:
    for pick in row.picks:
        if pick.source.endpoint == GET and pick.kind != "ask":
            by_response.setdefault(tuple(pick.source.paths), []).append((row.target, pick))
out: dict[str, list[dict[str, Any]]] = {}
for paths, labels in by_response.items():
    mirrored = [p for p in request for r in paths if as_response(p) == r]
    if len(mirrored) != len(paths):  # every path of the pick must exist on the request side
        continue
    for target, pick in labels:
        source = {"endpoint": REQ, "direction": "request", "paths": mirrored}
        new: dict[str, Any] = {"source": source, "kind": pick.kind}
        for key in ("target", "transform"):
            if getattr(pick, key):
                new[key] = getattr(pick, key)
        out.setdefault(target, []).append(new)
count = f"{sum(len(p) for p in out.values())} picks on {len(out)} rows"

if "--write" in sys.argv:
    target_sheet = Path(sys.argv[sys.argv.index("--write") + 1])
    head, *blocks = target_sheet.read_text().split("\n- target: ")
    for i, block in enumerate(blocks):
        target = block.split("\n", 1)[0].strip("'")
        if target not in out:
            continue
        added = "\n".join(pick_text(p) for p in out[target])
        if "  picks: []" in block:
            block = block.replace("  picks: []", "  picks:\n" + added)
        else:
            end = "\n\n" if block.endswith("\n\n") else "\n"
            block = block.rstrip("\n") + "\n" + added + end
        blocks[i] = block
    target_sheet.write_text("\n- target: ".join([head, *blocks]))
    print(f"inserted {count} into {target_sheet}")
else:
    for target, picks in out.items():
        print(f"# ---- add under: {target}")
        print(yaml.safe_dump(picks, sort_keys=False, width=1000, default_flow_style=None).rstrip())
    print(f"# {count} proposed", file=sys.stderr)
