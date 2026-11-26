# Real-time Voice Assistant (DE + EN)

A voice assistant for the shop floor. Ask in German or English ("Wie ist der Status von Linie 2?", "Create a maintenance ticket for machine 7.") and get a spoken answer in the same language. Response time is measured and optimized one stage at a time.

```
Silero VAD → faster-whisper (STT + language ID) → LLM + function calling ─┬─ get_line_status / create_ticket / list_alarms
                                                                           └─ LangGraph agent (complex questions)
                                                  → sentence streaming → Piper TTS
```

> 🚧 Work in progress. See [ROADMAP.md](ROADMAP.md) for the day-by-day plan and current status.

## Quickstart

```bash
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# optional: synthetic smoke-test WAVs (Windows built-in voices)
powershell -ExecutionPolicy Bypass -File scripts/make_synthetic_samples.ps1

python scripts/transcribe_files.py eval/samples   # VAD -> STT, per-stage timings in results/latency_raw.jsonl
pytest
```

## Repo structure

```
pipeline/   vad, stt, llm, tts modules + latency timing
functions/  callable tools + agent bridge
server/     push-to-talk app
eval/       test recordings, WER + latency scripts
results/    latency tables and charts
scripts/    CLI entry points
```
