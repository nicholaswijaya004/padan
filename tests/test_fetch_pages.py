# --- multi-page specs (method: pages) --------------------------------------------------------

from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from padan.fetch import (
    FetchOutcome,
    SpecEntry,
    fetch_pages,
    page_name,
    sha256_hex,
)

PAGE_A = "https://x.test/docs/storing.html"
PAGE_B = "https://x.test/docs/retrieving.html"
HTML_A = b"<html><body>storing</body></html>"
HTML_B = b"<html><body>retrieving</body></html>"
PAGES = SpecEntry(
    id="multi",
    url="https://x.test/docs/",
    format="html",
    usable="yes",
    method="pages",
    urls=[PAGE_A, PAGE_B],
)


def client_serving(pages: dict[str, bytes]) -> httpx.Client:
    """Fake server that answers each URL with its own body."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pages[str(request.url)])

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_page_name_is_last_path_segment_without_query() -> None:
    assert page_name("https://x.test/a/b/storing.html?v=2") == "storing.html"


def test_fetch_pages_saves_each_page_and_locks_it_separately(tmp_path: Path) -> None:
    lock: dict[str, str] = {}
    raw_dir = tmp_path / "raw"
    client = client_serving({PAGE_A: HTML_A, PAGE_B: HTML_B})

    outcomes = fetch_pages(PAGES, client, lock, raw_dir)

    assert outcomes == {
        "multi/storing.html": FetchOutcome.NEW,
        "multi/retrieving.html": FetchOutcome.NEW,
    }
    assert (raw_dir / "multi" / "storing.html").read_bytes() == HTML_A
    assert (raw_dir / "multi" / "retrieving.html").read_bytes() == HTML_B
    assert lock == {
        "multi/storing.html": sha256_hex(HTML_A),
        "multi/retrieving.html": sha256_hex(HTML_B),
    }


def test_fetch_pages_reports_only_the_page_that_changed(tmp_path: Path) -> None:
    lock = {"multi/storing.html": sha256_hex(HTML_A), "multi/retrieving.html": "old"}
    client = client_serving({PAGE_A: HTML_A, PAGE_B: HTML_B})

    outcomes = fetch_pages(PAGES, client, lock, tmp_path / "raw")

    assert outcomes == {
        "multi/storing.html": FetchOutcome.UNCHANGED,
        "multi/retrieving.html": FetchOutcome.CHANGED,
    }
    assert lock["multi/retrieving.html"] == "old"


BASE = {"id": "multi", "url": None, "format": "html", "usable": "yes"}


@pytest.mark.parametrize(
    "fields",
    [
        pytest.param({"method": "pages"}, id="pages-without-urls"),
        pytest.param({"method": "pages", "urls": [PAGE_A, PAGE_A]}, id="duplicate-page-names"),
        pytest.param({"method": "pages", "urls": ["https://x.test/docs/"]}, id="url-without-name"),
        pytest.param({"method": "direct", "urls": [PAGE_A]}, id="urls-without-pages-method"),
        pytest.param({"method": "page"}, id="unknown-method"),
    ],
)
def test_inconsistent_entries_are_rejected(fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        SpecEntry.model_validate(BASE | fields)
