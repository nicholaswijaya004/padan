"""Stage 1 extraction from XML examples inside HTML pages (HX / OpenTravel)."""

from pathlib import Path

import pytest

from padan.extract import (
    XmlElement,
    extract_pages,
    load_scoped,
    parse_xml,
    xml_blocks,
    xml_leaves,
)
from padan.fetch import page_name

REPO_ROOT = Path(__file__).resolve().parent.parent

PAGE = """
<h2>Simple Booking Example</h2>
<pre><code>POST https://bookings-stage.example.com/ota/rest/OTA_CruiseBookRQ
Content-Type: application/xml</code></pre>
<pre><code class="lang-xml">&lt;OTA_CruiseBookRQ xmlns="urn:ota" Version="1.00"&gt;
  &lt;SailingInfo&gt;&lt;SelectedSailing VoyageID="CS217"/&gt;&lt;/SailingInfo&gt;
&lt;/OTA_CruiseBookRQ&gt;</code></pre>
<h2>Response Example</h2>
<pre><code class="lang-xml">&lt;vx:OTA_CruiseBookRS xmlns:vx="urn:ota"&gt;
  &lt;vx:ReservationID ID="10277" StatusCode="42"/&gt;
&lt;/vx:OTA_CruiseBookRS&gt;</code></pre>
"""


# --- parse_xml (written by Claude) -------------------------------------------------------------


def test_parse_drops_prefixes_and_xmlns() -> None:
    root = parse_xml('<vx:Root xmlns:vx="urn:x" A="1"><vx:Child>hi</vx:Child></vx:Root>')
    assert (root.name, root.attrs) == ("Root", {"A": "1"})
    assert (root.children[0].name, root.children[0].text) == ("Child", "hi")


def test_parse_repairs_a_tag_swallowed_by_a_placeholder() -> None:
    # HX's OTA_CruiseBookRS: "[..]" replaced the closing </SelectedSailing>.
    root = parse_xml(
        '<RS><SailingInfo><SelectedSailing VoyageID="V1">[..]'
        '<SelectedCategory PricedCategoryCode="A"/></SailingInfo><PolicyInfo Name="T"/></RS>'
    )
    sailing_info, policy = root.children
    assert policy.name == "PolicyInfo"
    assert sailing_info.children[0].children[0].name == "SelectedCategory"


def test_xml_blocks_take_the_endpoint_from_the_request_line() -> None:
    blocks = xml_blocks(PAGE)
    assert [(b.endpoint, b.root.name) for b in blocks] == [
        ("POST /ota/rest/OTA_CruiseBookRQ", "OTA_CruiseBookRQ"),
        ("POST /ota/rest/OTA_CruiseBookRQ", "OTA_CruiseBookRS"),
    ]


# --- xml_leaves (written by Nicholas) ----------------------------------------------------------


def el(
    name: str, attrs: dict[str, str] | None = None, *children: XmlElement, text: str = ""
) -> XmlElement:
    return XmlElement(name, attrs or {}, list(children), text)


def test_leaves_attributes_use_at() -> None:
    root = el("RS", {"Version": "1"}, el("ReservationID", {"ID": "10277"}))
    assert xml_leaves(root) == [("@Version", "1"), ("ReservationID@ID", "10277")]


def test_leaves_text_of_a_leaf_element() -> None:
    root = el("RS", None, el("PersonName", None, el("GivenName", text=" Ana ")))
    assert xml_leaves(root) == [("PersonName.GivenName", "Ana")]


def test_leaves_skip_placeholder_text() -> None:
    root = el("RS", None, el("GuestDetails", text="[..guest details..]"))
    assert xml_leaves(root) == []


def test_leaves_repeated_children_get_brackets_and_first_value() -> None:
    root = el("RS", None, el("Information", {"Name": "A"}), el("Information", {"Name": "B"}))
    assert xml_leaves(root) == [("Information[]@Name", "A")]


def test_leaves_single_child_has_no_brackets() -> None:
    root = el("RS", None, el("GuestDetail", {"Ref": "1"}))
    assert xml_leaves(root) == [("GuestDetail@Ref", "1")]


# --- extract_pages -----------------------------------------------------------------------------


def test_extract_pages_picks_the_scoped_messages() -> None:
    fields = extract_pages([PAGE], ["OTA_CruiseBookRS response"], exclude=["ReservationID@Status"])
    assert [(f.endpoint, f.direction, f.path, f.evidence) for f in fields] == [
        (
            "POST /ota/rest/OTA_CruiseBookRQ",
            "response",
            "ReservationID@ID",
            "[no description; example: 10277]",
        )
    ]


def test_extract_pages_refuses_an_ambiguous_scope() -> None:
    with pytest.raises(ValueError):
        extract_pages([PAGE, PAGE], ["OTA_CruiseBookRQ request"], exclude=[])


# --- the real HX pages (needs data/raw/, so skipped in CI) -------------------------------------


def test_hx_scope_extracts_the_expected_messages() -> None:
    entry = load_scoped("hx-swota", REPO_ROOT / "data" / "manifest.yaml")
    files = [REPO_ROOT / "data" / "raw" / entry.id / page_name(url) for url in entry.urls]
    if not all(f.exists() for f in files):
        pytest.skip("data/raw/hx-swota/ not fetched (run make fetch)")
    fields = extract_pages([f.read_text() for f in files], entry.scope, entry.exclude)
    per_message = {(f.endpoint, f.direction): 0 for f in fields}
    for f in fields:
        per_message[(f.endpoint, f.direction)] += 1
    assert per_message == {
        ("POST /ota/rest/OTA_CruiseBookRQ", "request"): 7,
        ("POST /ota/rest/OTA_CruiseBookRQ", "response"): 50,
        ("POST /ota/rest/OTA_ReadRQ", "response"): 13,
    }
