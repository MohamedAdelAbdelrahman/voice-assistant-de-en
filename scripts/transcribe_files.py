"""Run VAD -> STT on audio files and log per-stage latency.

Usage:
    python scripts/transcribe_files.py eval/samples/*.wav
    python scripts/transcribe_files.py eval/samples --model base --log results/latency_raw.jsonl
    python scripts/transcribe_files.py eval/samples --no-vad      # STT on the untrimmed audio
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.stt import SpeechToText, load_audio  # noqa: E402
from pipeline.timing import LatencyLog  # noqa: E402
from pipeline.vad import VoiceActivityDetector  # noqa: E402

AUDIO_EXT = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(f for f in p.iterdir() if f.suffix.lower() in AUDIO_EXT)
        else:
            files.append(p)
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--model", default="small")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--compute-type", default="int8")
    ap.add_argument("--beam-size", type=int, default=5)
    ap.add_argument("--no-vad", action="store_true", help="skip silence trimming")
    ap.add_argument("--log", default="results/latency_raw.jsonl")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # umlauts on Windows consoles

    files = collect(args.paths)
    if not files:
        sys.exit("No audio files found.")

    log = LatencyLog(args.log)
    t0 = time.perf_counter()
    stt = SpeechToText(args.model, args.device, args.compute_type, beam_size=args.beam_size)
    print(f"model load: {(time.perf_counter() - t0):.1f}s", end="  |  ")
    t0 = time.perf_counter()
    stt.warmup()
    print(f"warmup: {(time.perf_counter() - t0):.1f}s")
    vad = None
    if not args.no_vad:
        vad = VoiceActivityDetector()
        vad.warmup()
    print()

    for f in files:
        log.new_run()
        meta = {"file": f.name, "model": args.model, "compute_type": args.compute_type}
        with log.stage("load_audio", **meta):
            audio = load_audio(f)
        vad_ms, vad_info = 0.0, ""
        if vad:
            with log.stage("vad", **meta) as out:
                res = vad.trim(audio)
                out.update(original_s=res.original_s, start_s=res.start_s, end_s=res.end_s)
            vad_ms = log.last("vad")["ms"]
            vad_info = f"  VAD {vad_ms:4.0f} ms ({res.original_s:.1f}s -> {len(res.audio) / 16000:.1f}s)"
            if not res.has_speech:
                print(f"[--      ] no speech{vad_info}  {f.name}")
                continue
            audio = res.audio
        with log.stage("stt", **meta) as out:
            tr = stt.transcribe(audio)
            out.update(language=tr.language, audio_s=tr.audio_s)
        ms = log.last("stt")["ms"]
        rtf = ms / 1000 / tr.audio_s if tr.audio_s else 0
        print(f"[{tr.language} {tr.language_prob:.2f}] STT {ms:6.0f} ms  RTF {rtf:.2f}{vad_info}  {f.name}")
        print(f"    {tr.text}")


if __name__ == "__main__":
    main()
