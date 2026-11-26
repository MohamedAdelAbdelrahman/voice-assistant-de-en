"""Tool-loop tests against a scripted fake of the streaming Messages API (no network)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import anthropic
import httpx2 as httpx
import pytest

from functions.tools import ShopFloor
from pipeline.llm import APOLOGY, Assistant


def text_block(t):
    return NS(type="text", text=t)


def tool_block(id_, name, inp):
    return NS(type="tool_use", id=id_, name=name, input=inp)


class FakeStream:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason = content, stop_reason

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        for block in self.content:
            yield NS(type="content_block_start", content_block=NS(type=block.type))
            if block.type == "text":
                for i in range(0, len(block.text), 5):  # chunked like real deltas
                    yield NS(type="text", text=block.text[i : i + 5])

    def get_final_message(self):
        usage = NS(input_tokens=100, output_tokens=20, cache_read_input_tokens=80)
        return NS(content=self.content, stop_reason=self.stop_reason, usage=usage, model="fake")


class FakeClient:
    """Returns one scripted response per request and records what was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []
        self.beta = NS(messages=NS(stream=self._stream))

    def _stream(self, **kwargs):
        self.requests.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeStream(*item)


def make(script, **kw):
    client = FakeClient(script)
    return Assistant(ShopFloor(), client=client, **kw), client


def test_plain_answer_streams_text():
    a, client = make([([text_block("Hallo, wie kann ich helfen?")], "end_turn")])
    chunks = list(a.stream("Hallo", "de"))
    assert "".join(chunks) == "Hallo, wie kann ich helfen?" and len(chunks) > 1
    assert a.last.requests == 1 and a.last.first_token_ms is not None
    sent = client.requests[0]["messages"]
    assert sent[-1] == {"role": "system", "content": "Reply in German."}


def test_tool_loop_runs_tool_and_returns_result():
    a, client = make([
        ([tool_block("t1", "get_line_status", {"line_id": 2})], "tool_use"),
        ([text_block("Linie 2 läuft eingeschränkt.")], "end_turn"),
    ])
    r = a.respond("Wie ist der Status von Linie 2?", "de")
    assert r.text == "Linie 2 läuft eingeschränkt."
    assert [(c.name, c.args, c.ok) for c in r.tool_calls] == [("get_line_status", {"line_id": 2}, True)]
    # second request carries the tool_result for t1
    last_user = client.requests[1]["messages"][-1]
    assert last_user["role"] == "user" and last_user["content"][0]["tool_use_id"] == "t1"
    assert '"degraded"' in last_user["content"][0]["content"]
    assert r.input_tokens == 200 and r.cache_read_tokens == 160


def test_text_around_tool_call_gets_a_space():
    a, _ = make([
        ([text_block("Moment."), tool_block("t1", "list_alarms", {})], "tool_use"),
        ([text_block("Es gibt sieben Alarme.")], "end_turn"),
    ])
    assert a.respond("Alarme?", "de").text == "Moment. Es gibt sieben Alarme."


def test_tool_error_is_flagged_for_the_model():
    a, client = make([
        ([tool_block("t1", "get_line_status", {"line_id": 9})], "tool_use"),
        ([text_block("Line 9 does not exist.")], "end_turn"),
    ])
    r = a.respond("Status of line 9?", "en")
    assert not r.tool_calls[0].ok
    assert client.requests[1]["messages"][-1]["content"][0]["is_error"] is True


def test_declined_confirmation_does_not_create_ticket():
    a, _ = make(
        [
            ([tool_block("t1", "create_ticket", {"machine_id": 7, "description": "overheated"})], "tool_use"),
            ([text_block("Okay, no ticket.")], "end_turn"),
        ],
        confirm=lambda name, args: False,
    )
    before = len(a.shop.data["tickets"])
    r = a.respond("Create a ticket for machine 7", "en")
    assert len(a.shop.data["tickets"]) == before and not r.tool_calls[0].ok


def test_truncated_tool_input_is_not_executed():
    a, _ = make([
        ([tool_block("t1", "create_ticket", {"machine_id": 7})], "max_tokens"),
        ([text_block("Sorry.")], "end_turn"),
    ])
    r = a.respond("ticket", "en")
    assert r.tool_calls == [] and r.text == "Sorry."


def test_api_error_yields_spoken_apology_and_rolls_back_history():
    err = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))
    a, _ = make([err])
    assert "".join(a.stream("Status Linie 1", "de")) == APOLOGY["de"]
    assert a.last.error and a.history == []


def test_history_is_append_only_across_turns():
    a, client = make([
        ([text_block("Hi.")], "end_turn"),
        ([text_block("Again.")], "end_turn"),
    ])
    a.respond("one", "en")
    a.respond("two", "en")
    first, second = client.requests[0]["messages"], client.requests[1]["messages"]
    assert second[: len(first)] == first  # prefix unchanged -> prompt cache stays valid


@pytest.mark.parametrize("lang,expected", [("de", "German"), ("en", "English"), ("fr", "English")])
def test_language_note(lang, expected):
    a, client = make([([text_block("x")], "end_turn")])
    a.respond("q", lang)
    assert client.requests[0]["messages"][-1]["content"] == f"Reply in {expected}."


def test_request_shape():
    a, client = make([([text_block("x")], "end_turn")])
    a.respond("q", "en")
    req = client.requests[0]
    assert req["model"] == "claude-haiku-5-5" and req["output_config"] == {"effort": "low"}
    assert "fallbacks" not in req  # Haiku has no server-side fallback
    assert all(t["eager_input_streaming"] for t in req["tools"])
    assert req["tools"][-1]["cache_control"] == {"type": "ephemeral"}


def test_fallback_enabled_for_opus():
    a, client = make([([text_block("x")], "end_turn")], model="claude-opus-5-5")
    a.respond("q", "en")
    assert client.requests[0]["fallbacks"] == "default"
