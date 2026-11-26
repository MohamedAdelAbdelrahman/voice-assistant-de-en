"""Ollama backend tool loop against a scripted fake client (no server needed)."""
from __future__ import annotations

from types import SimpleNamespace as NS

import httpx

from functions.tools import ShopFloor
from pipeline.llm import APOLOGY, make_assistant
from pipeline.llm_ollama import OllamaAssistant


def chunks(text="", tool_calls=None):
    """One scripted streamed response: text in 4-char pieces, tool calls, then done."""
    out = [NS(message=NS(content=text[i : i + 4], tool_calls=None), done=False) for i in range(0, len(text), 4)]
    calls = [NS(function=NS(name=n, arguments=a)) for n, a in (tool_calls or [])]
    out.append(NS(message=NS(content="", tool_calls=calls or None), done=True,
                  done_reason="stop", prompt_eval_count=50, eval_count=10))
    return out


class FakeOllama:
    def __init__(self, script):
        self.script, self.requests = list(script), []

    def chat(self, **kw):
        self.requests.append({**kw, "messages": list(kw["messages"])})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return iter(item)


def make(script, **kw):
    client = FakeOllama(script)
    return OllamaAssistant(ShopFloor(), client=client, **kw), client


def test_tool_loop():
    a, client = make([
        chunks(tool_calls=[("get_line_status", {"line_id": 3})]),
        chunks("Linie 3 steht."),
    ])
    r = a.respond("Status Linie 3?", "de")
    assert r.text == "Linie 3 steht." and r.requests == 2
    assert [(c.name, c.ok) for c in r.tool_calls] == [("get_line_status", True)]
    tool_msg = client.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and '"stopped"' in tool_msg["content"]
    assert client.requests[0]["think"] is False
    assert client.requests[0]["messages"][0]["role"] == "system"
    assert client.requests[0]["messages"][-1] == {"role": "system", "content": "Reply in German."}


def test_leading_whitespace_stripped_and_space_between_rounds():
    a, _ = make([
        chunks("\n\nMoment.", [("list_alarms", {"line_id": 3})]),
        chunks("Drei Alarme."),
    ])
    assert a.respond("Alarme Linie 3?", "de").text == "Moment. Drei Alarme."


def test_connection_error_gives_apology():
    a, _ = make([httpx.ConnectError("refused")])
    assert "".join(a.stream("hi", "en")) == APOLOGY["en"]
    assert a.last.error and a.history == []


def test_factory():
    assert isinstance(make_assistant("ollama", client=FakeOllama([])), OllamaAssistant)
    assert make_assistant("ollama", client=FakeOllama([])).model == "qwen2.5:3b"
