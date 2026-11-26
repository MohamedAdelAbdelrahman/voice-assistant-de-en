"""Local LLM backend via Ollama: free, offline, runs on the GPU if one fits the model.

Same interface as ``pipeline.llm.Assistant`` (``stream``, ``respond``, ``last``,
``reset``, ``warmup``, ``shop``), so the rest of the pipeline doesn't care which
backend answers.

Latency notes:
* ``keep_alive`` keeps the model in (V)RAM between turns - reloading costs seconds;
* the system prompt + tools are identical on every request, so Ollama can reuse
  the KV cache for that prefix instead of re-reading ~1.5k tokens each time;
* thinking is switched off (``think=False``): short lookups don't need it and
  thinking tokens would delay the first spoken word.
"""
from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterator

import httpx
import ollama

from functions.tools import ShopFloor, openai_tools
from pipeline.llm import APOLOGY, LANG_NAMES, SYSTEM_PROMPT, TurnResult, execute_tool
from pipeline.timing import LatencyLog

# Chosen on 6 DE/EN test questions (GTX 1650, 4 GB):
#   qwen2.5:3b         6/6 correct tool, 100% on GPU, 2-5 s per turn
#   qwen3:4b-instruct  1/6 - answered from imagination instead of calling tools
#   qwen3:4b           writes its reasoning into the answer despite think=False (minutes per turn)
DEFAULT_OLLAMA_MODEL = "qwen2.5:3b"


class OllamaAssistant:
    def __init__(
        self,
        shop: ShopFloor | None = None,
        model: str = DEFAULT_OLLAMA_MODEL,
        host: str | None = None,
        client: Any | None = None,
        log: LatencyLog | None = None,
        confirm: Callable[[str, dict[str, Any]], bool] | None = None,
        max_tool_rounds: int = 4,
        num_ctx: int = 3072,  # fits weights + KV cache in 4 GB VRAM; one turn needs ~1.7k
        num_predict: int = 200,  # hard cap per request: spoken answers are short
        temperature: float = 0.2,
        keep_alive: str = "30m",
    ) -> None:
        self.shop = shop or ShopFloor()
        self.model = model
        self.client = client or ollama.Client(host=host, timeout=120)
        self.log = log
        self.confirm = confirm
        self.max_tool_rounds = max_tool_rounds
        self.options = {"num_ctx": num_ctx, "num_predict": num_predict, "temperature": temperature}
        self.keep_alive = keep_alive
        self.tools = openai_tools()
        self.system = {"role": "system", "content": SYSTEM_PROMPT}
        self.history: list[dict[str, Any]] = []
        self.last = TurnResult(model=model)

    def reset(self) -> None:
        self.history = []

    def warmup(self) -> None:
        """Load the model into memory and prime the KV cache for the system prompt + tools."""
        saved = self.history
        try:
            for _ in self.stream("Hi", "en"):
                pass
        finally:
            self.history = saved

    def respond(self, text: str, language: str) -> TurnResult:
        for _ in self.stream(text, language):
            pass
        return self.last

    def stream(self, text: str, language: str) -> Iterator[str]:
        lang = language if language in LANG_NAMES else "en"
        result = self.last = TurnResult(model=self.model)
        t0 = time.perf_counter()
        start_len = len(self.history)
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "system", "content": f"Reply in {LANG_NAMES[lang]}."})

        try:
            while result.requests <= self.max_tool_rounds:
                tool_calls = yield from self._one_request(result, t0)
                if not tool_calls:
                    break
                for tc in tool_calls:
                    name, args = tc.function.name, tc.function.arguments
                    out = execute_tool(self.shop, name, args, self.confirm, result, self.log)
                    self.history.append(
                        {"role": "tool", "tool_name": name, "content": json.dumps(out, ensure_ascii=False)}
                    )
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as e:
            result.error = f"{type(e).__name__}: {e}"
            del self.history[start_len:]  # keep history consistent
            if result.first_token_ms is None:
                result.first_token_ms = round((time.perf_counter() - t0) * 1000, 1)
            result.text += APOLOGY[lang]
            yield APOLOGY[lang]

        result.total_ms = round((time.perf_counter() - t0) * 1000, 1)
        if self.log:
            self.log._write({
                "stage": "llm_turn", "ms": result.total_ms, "model": result.model, "backend": "ollama",
                "first_token_ms": result.first_token_ms, "requests": result.requests,
                "tools": [c.name for c in result.tool_calls], "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens, "error": result.error,
            })

    def _one_request(self, result: TurnResult, t0: float):
        """Stream one chat request; yields text, returns the tool calls it asked for."""
        result.requests += 1
        req_start = time.perf_counter()
        content, tool_calls = "", []
        new_request = True
        for chunk in self.client.chat(
            model=self.model,
            messages=[self.system, *self.history],
            tools=self.tools,
            stream=True,
            think=False,
            options=self.options,
            keep_alive=self.keep_alive,
        ):
            msg = chunk.message
            if msg.tool_calls:
                tool_calls.extend(msg.tool_calls)
            if msg.content:
                delta = msg.content
                if not content:
                    delta = delta.lstrip()  # small models often start with a newline
                    if not delta:
                        continue
                now = time.perf_counter()
                if new_request and self.log:
                    self.log._write({"stage": "llm_ttft", "ms": round((now - req_start) * 1000, 1),
                                     "request": result.requests})
                if result.first_token_ms is None:
                    result.first_token_ms = round((now - t0) * 1000, 1)
                    if self.log:
                        self.log.mark("llm_first_token")
                # Text before and after a tool round: keep a space between.
                if new_request and result.text and not result.text[-1].isspace():
                    result.text += " "
                    yield " "
                new_request = False
                content += delta
                result.text += delta
                yield delta
            if chunk.done:
                result.stop_reason = chunk.done_reason
                result.input_tokens += chunk.prompt_eval_count or 0
                result.output_tokens += chunk.eval_count or 0

        assistant_msg: dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = [
                {"function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in tool_calls
            ]
        self.history.append(assistant_msg)
        return tool_calls
