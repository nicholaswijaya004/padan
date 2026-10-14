"""Download partner specs listed in data/manifest.yaml, hash them, verify against the lock file."""

import hashlib
from enum import Enum

import httpx


class FetchOutcome(Enum):
    NEW = "new"  # no hash recorded for this spec yet → record it
    UNCHANGED = "unchanged"  # recorded hash matches the fresh one
    CHANGED = "changed"  # recorded hash differs → spec changed upstream


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
