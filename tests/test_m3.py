"""M3 step 4: the measurement over specs and label sources."""

from pathlib import Path

import pytest
import yaml

from padan import m3
from padan.m3 import JSONLike, examples, kind_of, label_file, measure

SPEC = """
openapi: 3.1.0
paths:
  /orders:
    post:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [ref, qty]
              properties:
                ref: {type: string}
                qty: {type: integer}
  /orders/{id}:
    get:
      responses:
        '200':
          content:
            application/json:
              schema: {type: object, properties: {state: {type: string}}}
              examples:
                one: {$ref: '#/components/examples/One'}
components:
  examples:
    One:
      value: {id: 'O-1', state: OK, placed: 2026-11-05}
"""

LABELS = """
- source: {endpoint: 'POST /orders', direction: request, paths: ['ref']}
  target: our_booking_id
  kind: direct
  evidence: 'Our reference.'
- source: {endpoint: 'GET /orders/{id}', direction: response, paths: ['id']}
  target: partner_booking_id
  kind: direct
  evidence: 'Order id.'
- source: {endpoint: 'GET /orders/{id}', direction: response, paths: ['state']}
  target: ASK_PARTNER
  candidate: status
  question: 'What does OK mean?'
  evidence: 'State.'
"""


def test_kind_of() -> None:
    assert kind_of("(body): 'qty' is a required property") == "missing"
    assert kind_of("qty: '2' is not of type 'integer'") == "type"
    assert kind_of("ref: 'x' is too long") == "other"


def test_json_like_types_values_but_keeps_dates_as_text() -> None:
    assert yaml.load("a: 1\nb: true\nc: null\nd: 2026-11-05", Loader=JSONLike) == {
        "a": 1,
        "b": True,
        "c": None,
        "d": "2026-11-05",
    }


def test_examples_follow_refs() -> None:
    spec = yaml.load(SPEC, Loader=JSONLike)
    assert examples(spec, "GET /orders/{id}") == [
        {"id": "O-1", "state": "OK", "placed": "2026-11-05"}
    ]
    assert examples(spec, "POST /orders") == []


def test_label_files() -> None:
    assert label_file("viator-partner", "gold") == Path(
        "data/labels/test-corrected/viator-partner.yaml"
    )
    assert label_file("octo-core", "gold") == Path("data/labels/octo-core.yaml")
    assert label_file("octo-core", "predicted").parts[-2:] == (m3.SYSTEM, "octo-core.yaml")


def test_measure_counts_requests_responses_and_todos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "demo.yaml").write_text(SPEC)
    labels = tmp_path / "labels.yaml"
    labels.write_text(LABELS)
    monkeypatch.setattr(m3, "RAW_DIR", tmp_path)
    report = measure("demo", labels)
    assert report["steps"] == {"direct": 2, "ask": 1}
    assert report["todos"] == 1
    assert report["requests"]["POST /orders"]["problems"] == {"missing": 1, "type": 0, "other": 0}
    (result,) = report["responses"]["GET /orders/{id}"]
    assert not result["valid"]
    assert "status" in result["fields"] and "partner_booking_id" not in result["fields"]
