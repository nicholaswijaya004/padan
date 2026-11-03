"""M3 step 1: labels as a plan, and the path runtime generated clients use."""

from typing import Any

from padan.labels import LabelEntry
from padan.plan import plan_from_labels
from padan.runtime import get, parts, put

SOURCE = {"endpoint": "GET /b", "direction": "response"}


def label(paths: list[str], target: str, **more: str) -> LabelEntry:
    return LabelEntry.model_validate(
        {"source": SOURCE | {"paths": paths}, "target": target, "evidence": "e."} | more
    )


def test_the_plan_drops_none_and_turns_an_ask_into_a_todo_on_its_candidate() -> None:
    plan = plan_from_labels(
        "demo",
        [
            label(["a"], "NONE"),
            label(["b"], "contact.email", kind="direct"),
            label(["c"], "ASK_PARTNER", candidate="status", question="Codes?"),
            label(["d", "e"], "travellers[].full_name", kind="derived", transform="d + e"),
        ],
    )
    assert [(s.sources, s.target, s.kind, s.detail) for s in plan.steps] == [
        (("b",), "contact.email", "direct", None),
        (("c",), "status", "ask", "Codes?"),
        (("d", "e"), "travellers[].full_name", "derived", "d + e"),
    ]
    assert plan.operations() == [("GET /b", "response")]
    assert plan.kinds() == {"direct": 1, "ask": 1, "derived": 1}


def test_parts() -> None:
    assert parts("a.b[].c[k=v].d[0]") == [("a", None), ("b", ""), ("c", "k=v"), ("d", "0")]
    assert parts("[].x") == [("", ""), ("x", None)]


PAYLOAD = {
    "id": "B1",
    "items": [
        {"travellers": [{"first": "Ana"}, {"first": "Ben"}], "codes": [{"t": "QR", "v": "1"}]},
        {"travellers": [{"first": "Cy"}], "codes": [{"t": "PDF", "v": "u"}]},
    ],
}


def test_get_flattens_selects_and_skips_missing() -> None:
    assert get(PAYLOAD, "id") == ["B1"]
    assert get(PAYLOAD, "items[].travellers[].first") == ["Ana", "Ben", "Cy"]
    assert get(PAYLOAD, "items[0].travellers[].first") == ["Ana", "Ben"]
    assert get(PAYLOAD, "items[].codes[t=PDF].v") == ["u"]
    assert get(PAYLOAD, "missing.path") == []
    assert get([{"x": 1}, {"x": 2}], "[].x") == [1, 2]


def test_put_fills_the_first_list_level_element_by_element() -> None:
    record: dict[str, Any] = {}
    put(record, "travellers[].given_name", ["Ana", "Ben"])
    put(record, "travellers[].family_name", ["Ng", "Ito"])
    put(record, "contact.email", ["a@x.io", "ignored@x.io"])
    put(record, "contact.phones[]", ["+1", "+2"])
    assert record == {
        "travellers": [
            {"given_name": "Ana", "family_name": "Ng"},
            {"given_name": "Ben", "family_name": "Ito"},
        ],
        "contact": {"email": "a@x.io", "phones": ["+1", "+2"]},
    }


def test_put_with_a_filter_counts_and_creates_only_matching_elements() -> None:
    record: dict[str, Any] = {}
    put(record, "fulfilment[kind=voucher].value", ["v1"])
    put(record, "fulfilment[kind=ticket].value", ["t1", "t2"])
    put(record, "fulfilment[kind=ticket].format", ["qrcode", "qrcode"])
    assert record["fulfilment"] == [
        {"kind": "voucher", "value": "v1"},
        {"kind": "ticket", "value": "t1", "format": "qrcode"},
        {"kind": "ticket", "value": "t2", "format": "qrcode"},
    ]


def test_put_deeper_list_levels_get_a_new_element_per_value() -> None:
    record: dict[str, Any] = {}
    put(record, "travellers[].custom_fields[].value", ["diet A", "diet B"])
    assert record == {
        "travellers": [
            {"custom_fields": [{"value": "diet A"}]},
            {"custom_fields": [{"value": "diet B"}]},
        ]
    }
