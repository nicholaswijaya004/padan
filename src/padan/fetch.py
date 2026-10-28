"""Download partner specs listed in data/manifest.yaml, hash them, verify against the lock file."""

import hashlib
import io
import json
import re
import tarfile
import tempfile
from collections.abc import Callable
from enum import Enum
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
import yaml
from pydantic import BaseModel, model_validator

from padan.bundle import bundle, dump

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
    method: Literal["direct", "pages", "redoc", "github"] | None = None
    urls: list[str] = []
    commit: str | None = None  # method github: the pinned commit
    root: str | None = None  # method github: the spec's entry file inside the repository

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
        if self.method == "github":
            if not (self.url or "").startswith("https://github.com/"):
                raise ValueError(f"{self.id}: method 'github' needs a github.com url")
            if not re.fullmatch(r"[0-9a-f]{40}", self.commit or ""):
                raise ValueError(f"{self.id}: method 'github' needs a full commit hash")
            if not self.root:
                raise ValueError(f"{self.id}: method 'github' needs root")
        elif self.commit or self.root:
            raise ValueError(f"{self.id}: commit/root given but method is {self.method!r}")
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


REDOC_MARKER = "__redoc_state = "


def redoc_spec(page: bytes) -> bytes:
    """The OpenAPI document a Redoc page embeds (`__redoc_state = {...};`), as YAML."""
    html = page.decode("utf-8")
    start = html.find(REDOC_MARKER)
    if start == -1:
        raise NotASpecError("no __redoc_state in the page")
    try:
        state, _ = json.JSONDecoder().raw_decode(html, start + len(REDOC_MARKER))
        spec = state["spec"]["data"]
    except (ValueError, KeyError, TypeError) as e:
        raise NotASpecError("__redoc_state holds no spec") from e
    return dump(spec)


def github_spec(tarball: bytes, root: str) -> bytes:
    """Unpack a GitHub source tarball and bundle the spec that starts at `root`, as YAML."""
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(tarball), mode="r:gz") as archive:
            archive.extractall(tmp, filter="data")  # refuses absolute paths, links out, devices
        (top,) = Path(tmp).iterdir()  # GitHub wraps the tree in one <repo>-<commit>/ folder
        return dump(bundle(top / root, within=top))


def tarball_url(entry: SpecEntry) -> str:
    """https://github.com/owner/repo -> its source tarball at the pinned commit."""
    owner_repo = urlsplit(entry.url or "").path.strip("/")
    return f"https://codeload.github.com/{owner_repo}/tar.gz/{entry.commit}"


def load_manifest(path: Path) -> list[SpecEntry]:
    """Read the manifest YAML into validated SpecEntry objects."""
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [SpecEntry.model_validate(entry) for entry in raw]


def fetch_file(
    key: str,
    url: str,
    fmt: str,
    client: httpx.Client,
    lock: dict[str, str],
    path: Path,
    derive: Callable[[bytes], bytes] | None = None,
) -> FetchOutcome:
    """Download one file, verify it, and compare its hash with lock[key].

    `derive` turns the download into the spec (a Redoc page -> its OpenAPI); the spec is what gets
    checked, hashed and saved. Saves the file on NEW or UNCHANGED; records the hash only on NEW;
    on CHANGED leaves both the file and the lock untouched.
    """
    data = download(url, client)
    if derive is not None:
        data = derive(data)
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
    """Fetch a single-file spec to raw_dir/<id>.<ext>, locked under its id.

    direct: the URL is the spec. redoc: the spec is embedded in the page. github: the spec is
    bundled from the repository's tarball at the pinned commit.
    """
    if entry.url is None or entry.format is None:
        raise ValueError(f"{entry.id}: no url or format in the manifest")

    path = raw_dir / f"{entry.id}.{EXTENSIONS[entry.format]}"
    url = entry.url
    derive: Callable[[bytes], bytes] | None = None
    if entry.method == "redoc":
        derive = redoc_spec
    elif entry.method == "github":
        root = entry.root or ""

        def derive_github(tarball: bytes) -> bytes:
            return github_spec(tarball, root)

        url, derive = tarball_url(entry), derive_github
    return fetch_file(entry.id, url, entry.format, client, lock, path, derive)


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
            except (httpx.HTTPError, NotASpecError, ValueError, KeyError, tarfile.TarError) as e:
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
