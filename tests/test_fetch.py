from pathlib import Path

import httpx
import pytest

from padan.fetch import (
    FetchOutcome,
    NotASpecError,
    SpecEntry,
    check_looks_like_spec,
    decide,
    download,
    fetch_one,
    load_manifest,
    sha256_hex,
)


def client_returning(status: int, body: bytes) -> httpx.Client:
    """A client whose every request gets the same canned response; no network."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


ENTRY = SpecEntry(
    id="demo", url="https://x.test/a.yaml", format="openapi", usable="yes", method="direct"
)
BODY = b"openapi: 3.0.0\n"

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_sha256_of_empty_input_matches_known_value() -> None:
    # The SHA-256 of zero bytes is a published constant:
    # if this passes, we're calling the real SHA-256.
    assert sha256_hex(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_same_input_gives_same_hash() -> None:
    hash1 = sha256_hex(b"hello, world!")
    hash2 = sha256_hex(b"hello, world!")
    assert hash1 == hash2


def test_one_byte_change_gives_different_hash() -> None:
    hash1 = sha256_hex(b"openapi: 3.0.0")
    hash2 = sha256_hex(b"openapi: 3.0.1")
    assert hash1 != hash2


def test_decide_new_when_spec_not_in_lock() -> None:
    lock: dict[str, str] = {}
    assert decide("musement-partner", "aaa", lock) == FetchOutcome.NEW


def test_decide_unchanged_when_digest_matches() -> None:
    lock = {"musement-partner": "aaa"}
    assert decide("musement-partner", "aaa", lock) == FetchOutcome.UNCHANGED


def test_decide_changed_when_digest_differs() -> None:
    lock = {"musement-partner": "aaa"}
    assert decide("musement-partner", "bbb", lock) == FetchOutcome.CHANGED


def test_download_returns_body_on_200() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"hello, world!")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    body = download("https://example.com/spec.yaml", client)
    assert body == b"hello, world!"


def test_download_raises_on_403() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, content=b"forbidden")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        download("https://example.com/spec.yaml", client)


def test_check_accepts_openapi_yaml() -> None:
    # No assert needed: if the function raises, pytest fails this test.
    check_looks_like_spec(b"openapi: 3.0.0\ninfo:\n  title: X\n", "openapi")


def test_check_rejects_empty_body() -> None:
    with pytest.raises(NotASpecError):
        check_looks_like_spec(b"", "openapi")


def test_check_accepts_openapi_json() -> None:
    check_looks_like_spec(b'{"openapi": "3.0.0", "info": {"title": "X"}}', "openapi")


def test_check_rejects_html_soft_404() -> None:
    with pytest.raises(NotASpecError):
        check_looks_like_spec(b"<html><body>Not Found</body></html>", "openapi")


def test_check_rejects_yaml_without_openapi_key() -> None:
    with pytest.raises(NotASpecError):
        check_looks_like_spec(b"info:\n  title: X\n", "openapi")


def test_check_rejects_broken_yaml_as_not_a_spec() -> None:
    with pytest.raises(NotASpecError):
        check_looks_like_spec(b"openapi: 3.0.0\ninfo:\n  title: X\n  version: [1,2,3", "openapi")


def test_check_accepts_html() -> None:
    check_looks_like_spec(b"<html><body>Hello</body></html>", "html")


def test_check_rejects_non_html_as_html() -> None:
    with pytest.raises(NotASpecError):
        check_looks_like_spec(b"openapi: 3.0.0\ninfo:\n  title: X\n", "html")


def test_load_manifest_reads_entries_and_ignores_extra_fields(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "- id: demo\n  url: https://x.test/a.yaml\n  format: openapi\n"
        '  usable: "yes"\n  method: direct\n  provider: Demo Inc\n'
    )
    entries = load_manifest(manifest)
    assert len(entries) == 1
    assert entries[0].id == "demo"
    assert entries[0].method == "direct"


def test_real_manifest_is_valid() -> None:
    entries = load_manifest(REPO_ROOT / "data" / "manifest.yaml")
    assert len(entries) > 0


def test_fetch_one_new_saves_file_and_records_hash(tmp_path: Path) -> None:
    lock: dict[str, str] = {}
    raw_dir = tmp_path / "raw"

    outcome = fetch_one(ENTRY, client_returning(200, BODY), lock, raw_dir)

    assert outcome == FetchOutcome.NEW
    assert (raw_dir / "demo.yaml").read_bytes() == BODY
    assert lock["demo"] == sha256_hex(BODY)


def test_fetch_one_unchanged_restores_file(tmp_path: Path) -> None:
    lock = {"demo": sha256_hex(BODY)}
    raw_dir = tmp_path / "raw"

    outcome = fetch_one(ENTRY, client_returning(200, BODY), lock, raw_dir)

    assert outcome == FetchOutcome.UNCHANGED
    assert (raw_dir / "demo.yaml").read_bytes() == BODY
    assert lock == {"demo": sha256_hex(BODY)}


def test_fetch_one_changed_keeps_lock_and_writes_nothing(tmp_path: Path) -> None:
    lock = {"demo": "old"}
    raw_dir = tmp_path / "raw"

    outcome = fetch_one(ENTRY, client_returning(200, BODY), lock, raw_dir)

    assert outcome == FetchOutcome.CHANGED
    assert lock == {"demo": "old"}
    assert not (raw_dir / "demo.yaml").exists()


def test_fetch_one_soft_404_raises_and_writes_nothing(tmp_path: Path) -> None:
    lock: dict[str, str] = {}
    raw_dir = tmp_path / "raw"
    soft_404 = client_returning(200, b"<html><body>Not found</body></html>")

    with pytest.raises(NotASpecError):
        fetch_one(ENTRY, soft_404, lock, raw_dir)

    assert lock == {}
    assert not (raw_dir / "demo.yaml").exists()
