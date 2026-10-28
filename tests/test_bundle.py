"""Bundling a spec split across files (GetYourGuide's layout) into one document."""

from pathlib import Path

import pytest
import yaml

from padan.bundle import bundle, dump, pointer_get
from padan.extract import extract


def write(folder: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)


SPEC = {
    "spec/api.yaml": """
openapi: 3.0.0
paths:
  /bookings:
    $ref: paths/bookings.yaml
components:
  schemas:
    Money: {type: object, properties: {amount: {type: string}}}
""",
    "spec/paths/bookings.yaml": """
post:
  requestBody:
    content:
      application/json:
        schema: {$ref: '#/Body'}
Body:
  type: object
  properties:
    id: {$ref: '../commons/fields.yaml#/BookingId'}
    price: {$ref: '#/components/schemas/Money'}
components:
  schemas:
    Money: {type: object, properties: {local: {type: string}}}
""",
    "spec/commons/fields.yaml": """
BookingId: {type: string, example: 1.10}
""",
}


def test_pointer_get_unescapes_and_indexes() -> None:
    document = {"a/b": [{"x": 1}], "~": 2}
    assert pointer_get(document, "/a~1b/0/x") == 1
    assert pointer_get(document, "/~0") == 2
    assert pointer_get(document, "") is document


def test_file_refs_are_inlined_and_hash_refs_point_into_their_own_file(tmp_path: Path) -> None:
    write(tmp_path, SPEC)
    document = bundle(tmp_path / "spec/api.yaml")
    body = document["paths"]["/bookings"]["post"]["requestBody"]["content"]["application/json"]
    properties = body["schema"]["properties"]
    assert properties["id"] == {"type": "string", "example": "1.10"}  # BaseLoader: text kept
    assert properties["price"] == {"type": "object", "properties": {"local": {"type": "string"}}}
    assert document["components"]["schemas"]["Money"]["properties"] == {
        "amount": {"type": "string"}
    }


def test_a_cycle_is_lifted_into_components_and_the_extractor_follows_it(tmp_path: Path) -> None:
    write(
        tmp_path,
        {
            "api.yaml": """
openapi: 3.0.0
paths:
  /bookings:
    post:
      requestBody:
        content:
          application/json:
            schema: {$ref: 'schema.yaml#/Node'}
""",
            "schema.yaml": """
Node:
  type: object
  properties:
    name: {type: string}
    child: {$ref: '#/Node'}
""",
        },
    )
    document = bundle(tmp_path / "api.yaml")
    assert set(document["components"]["schemas"]) == {"schema_Node"}
    fields = extract(document, ["POST /bookings request"], [])
    assert [f.path for f in fields] == ["name", "child.name", "child.child"]


def test_a_ref_may_not_leave_the_spec_folder(tmp_path: Path) -> None:
    write(tmp_path, {"outside.yaml": "X: {type: string}\n"})
    write(tmp_path, {"spec/api.yaml": "openapi: 3.0.0\npaths: {$ref: '../outside.yaml#/X'}\n"})
    with pytest.raises(ValueError, match="leaves"):
        bundle(tmp_path / "spec/api.yaml")


def test_dump_round_trips_strings(tmp_path: Path) -> None:
    write(tmp_path, SPEC)
    document = bundle(tmp_path / "spec/api.yaml")
    assert yaml.load(dump(document), Loader=yaml.BaseLoader) == document
