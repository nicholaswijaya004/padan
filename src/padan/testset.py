"""The test set as the run tools see it (ADR-001 Amendment 6).

Nothing reads a test label file unless every one of them is frozen and unchanged, and the systems
never read the gold at all: on test they get the scoped fields straight from extraction. (On dev the
fields come from the gold file, so a derived label's second field gets the first field's evidence.)
"""

import json
from pathlib import Path

from padan.extract import load_scoped, scoped_fields
from padan.sheet import FROZEN, TEST_DIR, verify

SystemField = tuple[str, str, str, str]  # endpoint, direction, path, evidence (baselines.Field)
FLAG = "--test"


def split_test_flag(argv: list[str]) -> tuple[bool, list[str]]:
    """(`--test` was given, the other arguments)."""
    return FLAG in argv, [arg for arg in argv if arg != FLAG]


def sealed_gold() -> list[Path]:
    """The test label files, if every one is frozen and unchanged; otherwise stop, with reasons."""
    recorded: dict[str, str] = json.loads(FROZEN.read_text()) if FROZEN.exists() else {}
    files = sorted(TEST_DIR.glob("*.yaml"))
    problems = verify(TEST_DIR, recorded)
    problems += [f"not frozen  {path.name}" for path in files if path.name not in recorded]
    if not files:
        problems.append(f"no label files in {TEST_DIR}")
    if problems:
        raise SystemExit("test labels are not sealed:\n  " + "\n  ".join(problems))
    return files


def system_fields(spec_id: str) -> list[SystemField]:
    """What a system sees on test: the scoped extraction, never the gold file."""
    entry = load_scoped(spec_id)
    return [(f.endpoint, f.direction, f.path, f.evidence) for f in scoped_fields(entry)]
