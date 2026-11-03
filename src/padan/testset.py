"""The test set as the run tools see it (ADR-001 Amendment 6).

Nothing reads a test label file unless every one of them is frozen and unchanged, and the systems
never read the gold at all: on test they get the scoped fields straight from extraction. (On dev the
fields come from the gold file, so a derived label's second field gets the first field's evidence.)
"""

import json
from pathlib import Path

from padan.extract import load_scoped, scoped_fields
from padan.sheet import CORRECTED_DIR, FROZEN, TEST_DIR, verify

SystemField = tuple[str, str, str, str]  # endpoint, direction, path, evidence (baselines.Field)
FLAG = "--test"


def split_test_flag(argv: list[str]) -> tuple[bool, list[str]]:
    """(`--test` was given, the other arguments)."""
    return FLAG in argv, [arg for arg in argv if arg != FLAG]


def sealed_gold(corrected: bool = False) -> list[Path]:
    """The test label files (or their corrected copy), if every one is frozen and unchanged;
    otherwise stop, with reasons."""
    test_dir = CORRECTED_DIR if corrected else TEST_DIR
    frozen = test_dir / "frozen.json" if corrected else FROZEN
    recorded: dict[str, str] = json.loads(frozen.read_text()) if frozen.exists() else {}
    files = sorted(test_dir.glob("*.yaml"))
    problems = verify(test_dir, recorded)
    problems += [f"not frozen  {path.name}" for path in files if path.name not in recorded]
    if not files:
        problems.append(f"no label files in {test_dir}")
    if problems:
        raise SystemExit("test labels are not sealed:\n  " + "\n  ".join(problems))
    return files


def system_fields(spec_id: str) -> list[SystemField]:
    """What a system sees on test: the scoped extraction, never the gold file."""
    entry = load_scoped(spec_id)
    return [(f.endpoint, f.direction, f.path, f.evidence) for f in scoped_fields(entry)]
