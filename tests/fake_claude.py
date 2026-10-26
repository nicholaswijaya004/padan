"""A stand-in for anthropic.Anthropic: scripted replies, recorded requests, no spend."""

import json
from types import SimpleNamespace as NS
from typing import Any

REFUSE = "REFUSE"


class FakeMessages:
    def __init__(self, replies: list[Any]) -> None:
        self.replies, self.calls = list(replies), []  # type: list[Any], list[dict[str, Any]]

    def create(self, **request: Any) -> NS:
        self.calls.append(request)
        reply = self.replies.pop(0)
        usage = NS(
            input_tokens=300,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=0,
            output_tokens=500,
        )
        if reply == REFUSE:
            return NS(stop_reason="refusal", content=[], model=request["model"], usage=usage)
        text = NS(type="text", text=json.dumps(reply))
        return NS(stop_reason="end_turn", content=[text], model=request["model"], usage=usage)


class FakeClient:
    def __init__(self, replies: list[Any]) -> None:
        self.beta = NS(messages=FakeMessages(replies))

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.beta.messages.calls  # type: ignore[no-any-return]


def reply(
    decision: str, *mappings: tuple[str, str], candidate: str = "", question: str = ""
) -> dict[str, Any]:
    return {
        "decision": decision,
        "mappings": [{"target": t, "transform": tr} for t, tr in mappings],
        "candidate": candidate,
        "question": question,
        "reason": "test",
    }
