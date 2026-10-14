import httpx
import pytest

from padan.fetch import (
    FetchOutcome,
    NotASpecError,
    check_looks_like_spec,
    decide,
    download,
    sha256_hex,
)


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
