"""Fetch methods that derive the spec from the download: redoc (a page) and github (a tarball)."""

import io
import json
import tarfile
from pathlib import Path

import httpx
import pytest
import yaml
from pydantic import ValidationError

from padan.fetch import (
    FetchOutcome,
    NotASpecError,
    SpecEntry,
    fetch_one,
    github_spec,
    redoc_spec,
    sha256_hex,
    tarball_url,
)

SPEC = {"openapi": "3.0.1", "paths": {"/booking/book": {}}}
PAGE = (
    "<html><script>const __redoc_state = " + json.dumps({"spec": {"data": SPEC}}) + ";</script>"
).encode()
COMMIT = "12c9da41c8d97c59f9232d580837bc000b5f0c1d"
GITHUB = SpecEntry(
    id="gh",
    url="https://github.com/acme/api-spec",
    format="openapi",
    usable="yes",
    method="github",
    commit=COMMIT,
    root="spec/api.yaml",
)


def tarball(files: dict[str, str]) -> bytes:
    """A gzipped tarball shaped like GitHub's: everything under one <repo>-<commit>/ folder."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"api-spec-{COMMIT}/{name}")
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_redoc_spec_takes_the_embedded_openapi() -> None:
    assert yaml.load(redoc_spec(PAGE), Loader=yaml.BaseLoader) == SPEC


def test_redoc_spec_refuses_a_page_without_state() -> None:
    with pytest.raises(NotASpecError):
        redoc_spec(b"<html>bot check</html>")


def test_github_spec_bundles_from_root() -> None:
    data = tarball(
        {
            "spec/api.yaml": "openapi: 3.0.0\npaths: {$ref: 'paths.yaml#/All'}\n",
            "spec/paths.yaml": "All: {/bookings: {}}\n",
        }
    )
    assert yaml.load(github_spec(data, "spec/api.yaml"), Loader=yaml.BaseLoader) == {
        "openapi": "3.0.0",
        "paths": {"/bookings": {}},
    }


def test_tarball_url_pins_the_commit() -> None:
    assert tarball_url(GITHUB) == f"https://codeload.github.com/acme/api-spec/tar.gz/{COMMIT}"


@pytest.mark.parametrize(
    "change",
    [{"commit": "main"}, {"root": None}, {"url": "https://gitlab.com/acme/api-spec"}],
)
def test_github_entries_need_a_github_url_full_commit_and_root(
    change: dict[str, str | None],
) -> None:
    with pytest.raises(ValidationError):
        SpecEntry.model_validate(GITHUB.model_dump() | change)


def test_commit_is_only_for_github() -> None:
    with pytest.raises(ValidationError, match="commit/root"):
        SpecEntry.model_validate(GITHUB.model_dump() | {"method": "direct"})


def test_fetch_one_redoc_saves_and_locks_the_derived_spec(tmp_path: Path) -> None:
    entry = SpecEntry(
        id="v", url="https://x.test/docs/", format="openapi", usable="yes", method="redoc"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=PAGE))
    )
    lock: dict[str, str] = {}
    assert fetch_one(entry, client, lock, tmp_path) == FetchOutcome.NEW
    saved = (tmp_path / "v.yaml").read_bytes()
    assert saved == redoc_spec(PAGE)
    assert lock == {"v": sha256_hex(saved)}
