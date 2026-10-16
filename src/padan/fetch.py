"""Download partner specs listed in data/manifest.yaml, hash them, verify against the lock file."""

import hashlib
import json
from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
import yaml
from pydantic import BaseModel, model_validator

EXTENSIONS = {"openapi": "yaml", "html": "html", "pdf": "pdf"}


class FetchOutcome(Enum):
    NEW = "new"  # no hash recorded for this spec yet → record it
    UNCHANGED = "unchanged"  # recorded hash matches the fresh one
    CHANGED = "changed"  # recorded hash differs → spec changed upstream


class NotASpecError(ValueError):
    """The downloaded bytes are not a spec of the expected format."""


def page_name(url: str) -> str:
    """File name a page is saved under: the last segment of the URL path (query ignored)."""
    return urlsplit(url).path.rsplit("/", 1)[-1]


class SpecEntry(BaseModel):
    """One manifest entry: only the fields the fetcher needs."""

    id: str
    url: str | None
    format: str | None
    usable: Literal["yes", "no", "unknown"]
    method: Literal["direct", "pages"] | None = None
    urls: list[str] = []

    @model_validator(mode="after")
    def pages_are_consistent(self) -> "SpecEntry":
        if self.method == "pages" and not self.urls:
            raise ValueError(f"{self.id}: method 'pages' needs urls")
        if self.urls and self.method != "pages":
            raise ValueError(f"{self.id}: urls given but method is {self.method!r}")
        names = [page_name(url) for url in self.urls]
        if "" in names:
            raise ValueError(f"{self.id}: a page URL has no file name")
        if len(set(names)) != len(names):
            raise ValueError(f"{self.id}: page file names are not unique")
        return self


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
            doc = yaml.load(data, Loader=yaml.BaseLoader)
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


def fetch_file(
    key: str, url: str, fmt: str, client: httpx.Client, lock: dict[str, str], path: Path
) -> FetchOutcome:
    """Download one file, verify it, and compare its hash with lock[key].

    Saves the file on NEW or UNCHANGED; records the hash only on NEW;
    on CHANGED leaves both the file and the lock untouched.
    """
    data = download(url, client)
    check_looks_like_spec(data, fmt)
    digest = sha256_hex(data)
    decision = decide(key, digest, lock)

    if decision in (FetchOutcome.NEW, FetchOutcome.UNCHANGED):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    if decision == FetchOutcome.NEW:
        lock[key] = digest
    return decision


def fetch_one(
    entry: SpecEntry, client: httpx.Client, lock: dict[str, str], raw_dir: Path
) -> FetchOutcome:
    """Fetch a single-file spec (method: direct) to raw_dir/<id>.<ext>, locked under its id."""
    if entry.url is None or entry.format is None:
        raise ValueError(f"{entry.id}: no url or format in the manifest")

    path = raw_dir / f"{entry.id}.{EXTENSIONS[entry.format]}"
    return fetch_file(entry.id, entry.url, entry.format, client, lock, path)


def fetch_pages(
    entry: SpecEntry, client: httpx.Client, lock: dict[str, str], raw_dir: Path
) -> dict[str, FetchOutcome]:
    """Fetch a multi-page spec (method: pages) to raw_dir/<id>/<page>, locked per page."""
    if entry.format is None:
        raise ValueError(f"{entry.id}: no format in the manifest")

    outcomes: dict[str, FetchOutcome] = {}
    for url in entry.urls:
        name = page_name(url)
        key = f"{entry.id}/{name}"
        path = raw_dir / entry.id / name
        outcomes[key] = fetch_file(key, url, entry.format, client, lock, path)
    return outcomes


MANIFEST = Path("data/manifest.yaml")
LOCK = Path("data/specs.lock.json")
RAW_DIR = Path("data/raw")


def main() -> int:
    """Fetch every usable spec that has a method; return 0 if all verified, 1 otherwise."""
    entries = load_manifest(MANIFEST)
    lock: dict[str, str] = json.loads(LOCK.read_text()) if LOCK.exists() else {}
    failures: list[str] = []

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for entry in entries:
            if entry.usable != "yes" or entry.method is None:
                continue
            try:
                if entry.method == "pages":
                    outcomes = fetch_pages(entry, client, lock, RAW_DIR)
                else:
                    outcomes = {entry.id: fetch_one(entry, client, lock, RAW_DIR)}
            except (httpx.HTTPError, NotASpecError, ValueError) as e:
                print(f"FAIL  {entry.id}: {e}")
                failures.append(entry.id)
                continue
            for key, outcome in outcomes.items():
                print(f"{outcome.value:9} {key}")
                if outcome == FetchOutcome.CHANGED:
                    failures.append(key)

    LOCK.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n")
    print(f"{len(failures)} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
