"""Download partner specs listed in data/manifest.yaml, hash them, verify against the lock file."""

import hashlib
from enum import Enum
from pathlib import Path
from typing import Literal

import httpx
import yaml
from pydantic import BaseModel

EXTENSIONS = {"openapi": "yaml", "html": "html", "pdf": "pdf"}


class FetchOutcome(Enum):
    NEW = "new"  # no hash recorded for this spec yet → record it
    UNCHANGED = "unchanged"  # recorded hash matches the fresh one
    CHANGED = "changed"  # recorded hash differs → spec changed upstream


class NotASpecError(ValueError):
    """The downloaded bytes are not a spec of the expected format."""


class SpecEntry(BaseModel):
    """One manifest entry: only the fields the fetcher needs."""

    id: str
    url: str | None
    format: str | None
    usable: Literal["yes", "no", "unknown"]
    method: str | None = None


def sha256_hex(data: bytes) -> str:
    """SHA-256 of the raw bytes, as a 64-character hex string."""
    return hashlib.sha256(data).hexdigest()


def decide(spec_id: str, digest: str, lock: dict[str, str]) -> FetchOutcome:
    """Compare a freshly computed digest with what the lock file recorded. No I/O."""
    if spec_id not in lock:
        return FetchOutcome.NEW
    if lock[spec_id] == digest:
        return FetchOutcome.UNCHANGED
    return FetchOutcome.CHANGED


def download(url: str, client: httpx.Client) -> bytes:
    """Fetch the URL. Raise on any non-2xx status.

    Never return an error page as if it were the spec.
    """
    response = client.get(url)
    response.raise_for_status()
    return response.content


def check_looks_like_spec(data: bytes, fmt: str) -> None:
    """Raise NotASpecError if the bytes don't look like a spec of the expected format."""
    if not data:
        raise NotASpecError("empty body")

    if fmt == "openapi":
        try:
            doc = yaml.safe_load(data)
        except yaml.YAMLError as e:
            raise NotASpecError("not valid YAML/JSON") from e
        if not isinstance(doc, dict):
            raise NotASpecError("not a dictionary")
        if "openapi" not in doc and "swagger" not in doc:
            raise NotASpecError("no 'openapi' or 'swagger' key")
        return

    if fmt == "html":
        if b"<html" not in data[:500].lower():
            raise NotASpecError("no <html> tag")
        return

    if fmt == "pdf":
        if not data.startswith(b"%PDF-"):
            raise NotASpecError("no %PDF- header")
        return

    raise ValueError(f"no spec check for format {fmt!r}")


def load_manifest(path: Path) -> list[SpecEntry]:
    """Read the manifest YAML into validated SpecEntry objects."""
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [SpecEntry.model_validate(entry) for entry in raw]


def fetch_one(
    entry: SpecEntry, client: httpx.Client, lock: dict[str, str], raw_dir: Path
) -> FetchOutcome:
    """Download one spec, verify it, and compare its hash with the lock.

    Saves the file on NEW or UNCHANGED; records the hash only on NEW;
    on CHANGED leaves both the file and the lock untouched.
    """
    if entry.url is None or entry.format is None:
        raise ValueError(f"{entry.id}: no url or format in the manifest")

    data = download(entry.url, client)
    check_looks_like_spec(data, entry.format)
    digest = sha256_hex(data)
    decision = decide(entry.id, digest, lock)
    if decision in (FetchOutcome.NEW, FetchOutcome.UNCHANGED):
        raw_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{entry.id}.{EXTENSIONS[entry.format]}").write_bytes(data)
    if decision == FetchOutcome.NEW:
        lock[entry.id] = digest
    return decision
    # CHANGED: do nothing
    return decision
