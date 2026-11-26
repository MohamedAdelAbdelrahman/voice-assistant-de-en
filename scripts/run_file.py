"""End-to-end text pipeline on audio files: VAD -> STT -> LLM + tools -> answer.

Usage:
    python scripts/run_file.py eval/samples                      # local LLM via Ollama (free)
    python scripts/run_file.py eval/samples --llm-model qwen3:4b-instruct
    python scripts/run_file.py eval/samples --llm claude         # Claude API (paid)

Ollama: install from ollama.com, then `ollama pull qwen2.5:3b`.
Claude: ANTHROPIC_API_KEY in the environment or in a git-ignored .env file.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from functions.tools import ShopFloor  # noqa: E402
from pipeline.llm import make_assistant  # noqa: E402
from pipeline.stt import SpeechToText, load_audio  # noqa: E402
from pipeline.timing import LatencyLog  # noqa: E402
from pipeline.vad import VoiceActivityDetector  # noqa: E402
from scripts.transcribe_files import collect  # noqa: E402


def load_dotenv(path: Path = Path(__file__).resolve().parents[1] / ".env") -> None:
    """Minimal KEY=VALUE loader for the git-ignored .env file (no extra dependency)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--stt-model", default="small")
    ap.add_argument("--llm", default="ollama", choices=["ollama", "claude"], help="LLM backend")
    ap.add_argument("--llm-model", default=None, help="default: qwen2.5:3b (ollama) / claude-haiku-5-5")
    ap.add_argument("--effort", default="low", choices=["low", "medium", "high"], help="Claude only")
    ap.add_argument("--log", default="results/latency_raw.jsonl")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    files = collect(args.paths)
    if not files:
        sys.exit("No audio files found.")

    log = LatencyLog(args.log)
    t0 = time.perf_counter()
    vad = VoiceActivityDetector()
    vad.warmup()
    stt = SpeechToText(args.stt_model)
    stt.warmup()
    try:
        assistant = make_assistant(args.llm, args.llm_model, shop=ShopFloor(), effort=args.effort, log=log)
        assistant.warmup()
    except TypeError as e:
        if "authentication" not in str(e):
            raise
        sys.exit("No Claude API credentials found. Put ANTHROPIC_API_KEY=... into .env "
                 "(see .env.example) or run `ant auth login`.")
    if assistant.last.error:
        sys.exit(f"LLM warm-up failed: {assistant.last.error}")
    print(f"startup (load + warm up VAD, STT, LLM): {time.perf_counter() - t0:.1f}s\n")

    for f in files:
        # Each file is an independent conversation with fresh shop-floor data.
        assistant.shop = ShopFloor()
        assistant.reset()
        log.new_run()
        meta = {"file": f.name}

        audio = load_audio(f)
        with log.stage("vad", **meta):
            seg = vad.trim(audio)
        if not seg.has_speech:
            print(f"== {f.name}: no speech\n")
            continue
        with log.stage("stt", **meta) as out:
            tr = stt.transcribe(seg.audio)
            out["language"] = tr.language

        print(f"== {f.name}")
        print(f"  heard   [{tr.language}] {tr.text}")
        print("  answer  ", end="", flush=True)
        for delta in assistant.stream(tr.text, tr.language):
            print(delta, end="", flush=True)
        print()

        turn = assistant.last
        for c in turn.tool_calls:
            status = "ok" if c.ok else f"ERROR {c.result['error']}"
            print(f"  tool    {c.name}({json.dumps(c.args, ensure_ascii=False)}) -> {status}")
        if turn.error:
            print(f"  error   {turn.error}")
        print(
            f"  timing  VAD {log.last('vad')['ms']:.0f} ms | STT {log.last('stt')['ms']:.0f} ms | "
            f"LLM first token {turn.first_token_ms or 0:.0f} ms, total {turn.total_ms:.0f} ms "
            f"({turn.requests} requests, model {turn.model}"
            + (f", cache read {turn.cache_read_tokens} tok" if args.llm == "claude" else "") + ")\n"
        )


if __name__ == "__main__":
    main()
