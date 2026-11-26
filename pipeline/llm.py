"""LLM turn handling: Claude with streaming + tool calling over the shop-floor tools.

``Assistant.stream(text, language)`` yields answer text deltas as they arrive, so
the TTS stage (Day 5) can start speaking on the first complete sentence. Tool
calls run in between: Claude asks for a tool, we execute it locally, send the
result back and keep streaming until Claude writes the final answer.

Latency notes:
* the system prompt and tool list never change between requests, so they form a
  stable prompt-cache prefix; the reply language is passed as a mid-conversation
  system message instead of being formatted into the system prompt;
* effort is ``low`` by default: these are short lookups, not hard reasoning;
* default model is Claude Haiku 5.5 (lowest latency and cost); it is configurable
  (``--llm-model``) so Day 8 can compare it against Sonnet / Opus.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

import anthropic

from functions.tools import ShopFloor, anthropic_tools
from pipeline.timing import LatencyLog

DEFAULT_MODEL = "claude-haiku-5-5"  # fastest + cheapest; compare others on Day 8
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Models with server-side refusal fallback (Haiku has none).
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1", "claude-fable-5-2"}
MUTATING_TOOLS = {"create_ticket"}
LANG_NAMES = {"de": "German", "en": "English"}

SYSTEM_PROMPT = """\
You are the voice assistant on a factory shop floor. Workers talk to you through a \
headset while they work, in German or English. Your replies are converted to speech.

You know nothing about the current state of the plant. For every question about \
lines, machines, alarms or tickets, call a tool FIRST and answer only from its result.

How to answer:
- Answer in the language named in the latest system note.
- Keep it short: one to three spoken sentences. Lead with the answer itself.
- Plain spoken text only. No markdown, lists, tables, emojis or bullet points.
- Write numbers so they read naturally aloud ("Linie 2", "64 Teile pro Stunde", \
"87 Prozent"). Give alarm codes as written, e.g. E-204.
- Use the tools for every fact about lines, machines, alarms and tickets. Never guess \
or invent values. If a tool returns an error, say briefly what went wrong.
- Tool results contain German and English alarm texts; use the one that matches the reply language.
- Lines are numbered 1 to 5 and machines 1 to 12. If the user does not say which \
line or machine they mean and it matters, ask one short question.
- When the user asks for a maintenance ticket, call create_ticket with their \
description; pick priority high for safety issues, overheating, leaks or a stopped \
line, otherwise medium unless they say otherwise. The app asks the user to confirm.
- If a request is outside what the tools can do, say so in one sentence.
"""

APOLOGY = {
    "de": "Entschuldigung, ich kann gerade keine Antwort abrufen. Bitte versuche es gleich noch einmal.",
    "en": "Sorry, I can't get an answer right now. Please try again in a moment.",
}


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: dict[str, Any]
    ms: float

    @property
    def ok(self) -> bool:
        return "error" not in self.result


@dataclass
class TurnResult:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    requests: int = 0
    first_token_ms: float | None = None  # from stream() call to first answer text
    total_ms: float = 0.0
    stop_reason: str | None = None
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    error: str | None = None


def execute_tool(
    shop: ShopFloor,
    name: str,
    args: Any,
    confirm: Callable[[str, dict[str, Any]], bool] | None,
    result: TurnResult,
    log: LatencyLog | None,
) -> dict[str, Any]:
    """Run one tool call (shared by all LLM backends) and record it on the turn."""
    t = time.perf_counter()
    if not isinstance(args, dict):
        out = {"error": "INVALID_JSON: arguments must be a JSON object"}
        args = {}
    elif name in MUTATING_TOOLS and confirm and not confirm(name, args):
        out = {"error": "The user declined. Nothing was changed."}
    else:
        out = shop.call(name, args)
    ms = round((time.perf_counter() - t) * 1000, 2)
    result.tool_calls.append(ToolCall(name, args, out, ms))
    if log:
        log._write({"stage": "tool", "ms": ms, "tool": name, "ok": "error" not in out})
    return out


def make_assistant(backend: str = "ollama", model: str | None = None, **kwargs: Any):
    """Create the assistant for a backend: 'ollama' (local, free) or 'claude' (cloud API)."""
    if backend == "claude":
        return Assistant(model=model or DEFAULT_MODEL, **kwargs)
    if backend == "ollama":
        from pipeline.llm_ollama import DEFAULT_OLLAMA_MODEL, OllamaAssistant

        kwargs.pop("effort", None)  # Claude-only setting
        return OllamaAssistant(model=model or DEFAULT_OLLAMA_MODEL, **kwargs)
    raise ValueError(f"unknown LLM backend {backend!r} (use 'ollama' or 'claude')")


def _tools_for_streaming() -> list[dict[str, Any]]:
    tools = [dict(t, eager_input_streaming=True) for t in anthropic_tools()]
    # Cache breakpoint after the last tool: tools + system prompt form the stable prefix.
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools


class Assistant:
    def __init__(
        self,
        shop: ShopFloor | None = None,
        model: str = DEFAULT_MODEL,
        effort: str = "low",
        client: Any | None = None,
        log: LatencyLog | None = None,
        confirm: Callable[[str, dict[str, Any]], bool] | None = None,
        max_tool_rounds: int = 4,
        max_tokens: int = 16000,
    ) -> None:
        self.shop = shop or ShopFloor()
        self.model = model
        self.effort = effort
        self.client = client or anthropic.Anthropic(timeout=30.0, max_retries=2)
        self.log = log
        # Called before a data-changing tool runs; None = auto-approve (offline/file mode).
        # The live UI (Day 9) passes a callback that asks the user.
        self.confirm = confirm
        self.max_tool_rounds = max_tool_rounds
        self.max_tokens = max_tokens
        self.tools = _tools_for_streaming()
        self.system = [{"type": "text", "text": SYSTEM_PROMPT}]
        self.history: list[dict[str, Any]] = []
        self.last: TurnResult = TurnResult()

    def reset(self) -> None:
        self.history = []

    def warmup(self) -> None:
        """One tiny request so connection setup (TLS, DNS) and the prompt cache are hot."""
        saved = self.history
        try:
            for _ in self.stream("Hi", "en"):
                pass
        finally:
            self.history = saved

    # ------------------------------------------------------------------
    def respond(self, text: str, language: str) -> TurnResult:
        """Non-incremental convenience wrapper around ``stream``."""
        for _ in self.stream(text, language):
            pass
        return self.last

    def stream(self, text: str, language: str) -> Iterator[str]:
        """Yield the answer as text deltas. Details land in ``self.last`` when done."""
        lang = language if language in LANG_NAMES else "en"
        result = self.last = TurnResult(model=self.model)
        t0 = time.perf_counter()

        # Append-only history keeps the cached prefix valid across turns.
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "system", "content": f"Reply in {LANG_NAMES[lang]}."})

        json_retries = 0
        try:
            while result.requests <= self.max_tool_rounds:
                try:
                    response = yield from self._one_request(result, t0)
                    json_retries = 0
                except ValueError:
                    # Tool input JSON the SDK could not parse at all: re-issue the turn (bounded).
                    json_retries += 1
                    if json_retries > 2:
                        raise
                    continue

                self.history.append({"role": "assistant", "content": response.content})
                result.stop_reason = response.stop_reason
                result.model = getattr(response, "model", self.model)
                self._add_usage(result, response.usage)

                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if response.stop_reason == "refusal" or not tool_uses:
                    break
                if response.stop_reason == "max_tokens":
                    # A cut-off tool input can parse as a valid partial object: don't run it.
                    self.history.append({"role": "user", "content": [
                        {"type": "tool_result", "tool_use_id": b.id, "is_error": True,
                         "content": "Tool input was cut off. Answer the user without this tool."}
                        for b in tool_uses
                    ]})
                    continue

                self.history.append({"role": "user", "content": [
                    self._run_tool(b, result) for b in tool_uses
                ]})
        except (anthropic.APIConnectionError, anthropic.APIStatusError, ValueError) as e:
            result.error = f"{type(e).__name__}: {e}"
            # Leave the history consistent: drop the unanswered turn.
            self._rollback_to_last_user_turn()
            if result.first_token_ms is None:
                result.first_token_ms = (time.perf_counter() - t0) * 1000
            result.text += APOLOGY[lang]
            yield APOLOGY[lang]

        result.total_ms = round((time.perf_counter() - t0) * 1000, 1)
        if self.log:
            self.log._write({
                "stage": "llm_turn", "ms": result.total_ms, "model": result.model,
                "first_token_ms": result.first_token_ms, "requests": result.requests,
                "tools": [c.name for c in result.tool_calls], "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens, "cache_read_tokens": result.cache_read_tokens,
                "error": result.error,
            })

    # ------------------------------------------------------------------
    def _one_request(self, result: TurnResult, t0: float):
        """Stream one Messages request; yields text deltas, returns the final message."""
        result.requests += 1
        req_start = time.perf_counter()
        first_in_request = True
        extra: dict[str, Any] = {}
        if self.model in FALLBACK_MODELS:
            # Refusal fallback: if the model declines on policy grounds, the API re-runs
            # the request on the server-defined fallback model inside the same call.
            extra = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=self.system,
            tools=self.tools,
            messages=self.history,
            output_config={"effort": self.effort},
            **extra,
        ) as stream:
            new_block = False
            for event in stream:
                if event.type == "content_block_start" and event.content_block.type == "text":
                    new_block = True
                    continue
                if event.type != "text" or not event.text:
                    continue
                now = time.perf_counter()
                if first_in_request and self.log:
                    self.log._write({"stage": "llm_ttft", "ms": round((now - req_start) * 1000, 1),
                                     "request": result.requests})
                first_in_request = False
                if result.first_token_ms is None:
                    result.first_token_ms = round((now - t0) * 1000, 1)
                    if self.log:
                        self.log.mark("llm_first_token")
                # Text before and after a tool call arrives in separate blocks: keep a space between.
                if new_block and result.text and not result.text[-1].isspace() and not event.text[0].isspace():
                    result.text += " "
                    yield " "
                new_block = False
                result.text += event.text
                yield event.text
            return stream.get_final_message()

    def _run_tool(self, block: Any, result: TurnResult) -> dict[str, Any]:
        out = execute_tool(self.shop, block.name, block.input, self.confirm, result, self.log)
        return {
            "type": "tool_result",
            "tool_use_id": block.id,
            "content": json.dumps(out, ensure_ascii=False),
            **({"is_error": True} if "error" in out else {}),
        }

    @staticmethod
    def _add_usage(result: TurnResult, usage: Any) -> None:
        if usage is None:
            return
        result.input_tokens += getattr(usage, "input_tokens", 0) or 0
        result.output_tokens += getattr(usage, "output_tokens", 0) or 0
        result.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0

    def _rollback_to_last_user_turn(self) -> None:
        for i in range(len(self.history) - 1, -1, -1):
            msg = self.history[i]
            if msg["role"] == "user" and isinstance(msg["content"], str):
                del self.history[i:]
                return
