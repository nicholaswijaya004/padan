"""Rules over the whole manifest (ADR-001 Amendment 2)."""

from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ROLES = {"dev", "test", "held_out"}


def load_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = yaml.safe_load(
        (REPO_ROOT / "data" / "manifest.yaml").read_text()
    )
    return entries


def roles_by_family(entries: list[dict[str, Any]]) -> dict[str, set[str]]:
    """Roles each spec family appears in, counting every entry not ruled out (usable != "no")."""
    families: dict[str, set[str]] = defaultdict(set)
    for entry in entries:
        if entry["usable"] != "no":
            families[entry["spec_family"]].add(entry["role"])
    return families


def test_every_role_is_known() -> None:
    assert {entry["role"] for entry in load_entries()} <= ROLES


def test_no_family_crosses_roles() -> None:
    crossing = {f: r for f, r in roles_by_family(load_entries()).items() if len(r) > 1}
    assert crossing == {}


def test_crossing_counts_unknown_and_ignores_unusable() -> None:
    entries = [
        {"spec_family": "hotelbeds", "role": "dev", "usable": "yes"},
        {"spec_family": "hotelbeds", "role": "held_out", "usable": "unknown"},
        {"spec_family": "hotelbeds", "role": "test", "usable": "no"},
    ]
    assert roles_by_family(entries) == {"hotelbeds": {"dev", "held_out"}}
