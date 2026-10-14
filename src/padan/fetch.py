"""Download partner specs listed in data/manifest.yaml, hash them, verify against the lock file."""

import hashlib


def sha256_hex(data: bytes) -> str:
    """SHA-256 of the raw bytes, as a 64-character hex string."""
    return hashlib.sha256(data).hexdigest()
