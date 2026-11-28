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
    tool_msg, reminder = client.requests[1]["messages"][-2:]
    assert tool_msg["role"] == "tool" and '"stopped"' in tool_msg["content"]
    # language repeated after tool results (German data made the 3B model drift)
    assert reminder == {"role": "system", "content": "Reply in German."}
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


def test_manual_question_is_prefetched_before_the_llm():
    a, client = make([chunks("Laut Handbuch zuerst absperren.")])
    r = a.respond("Was muss ich tun, bevor ich eine Maschine öffne?", "de")
    assert r.prefetched and r.requests == 1
    assert [c.name for c in r.tool_calls] == ["ask_manual"]
    msgs = client.requests[0]["messages"]
    assert msgs[-3]["tool_calls"][0]["function"]["name"] == "ask_manual"
    assert msgs[-2]["role"] == "tool" and "handbook/de.md#LOTO" in msgs[-2]["content"]


def test_no_prefetch_for_status_questions_or_when_disabled():
    a, _ = make([chunks(tool_calls=[("get_line_status", {"line_id": 2})]), chunks("Linie 2 läuft.")])
    assert not a.respond("Wie ist der Status von Linie 2?", "de").prefetched
    a, client = make([chunks("Ok.")], route_manual=False)
    assert not a.respond("How do I reset the emergency stop?", "en").prefetched
    assert client.requests[0]["messages"][-1]["role"] == "system"


def test_no_prefetch_when_the_handbook_has_nothing():
    a, client = make([chunks(tool_calls=[("ask_manual", {"question": "E-999"})]), chunks("Nicht im Handbuch.")])
    r = a.respond("Was bedeutet E-999?", "de")
    assert not r.prefetched and r.requests == 2
