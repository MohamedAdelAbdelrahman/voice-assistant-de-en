# Real-time Voice Assistant (DE + EN)

A voice assistant for the shop floor. Ask in German or English ("Wie ist der Status von Linie 2?", "Create a maintenance ticket for machine 7.") and get a spoken answer in the same language. Response time is measured and optimized one stage at a time.

```
Silero VAD → faster-whisper (STT + language ID) → local LLM (Ollama) + function calling ─┬─ get_line_status / list_alarms / create_ticket
                                                                                         ├─ get_machine_telemetry (AI4I 2020 data)
                                                                                         └─ ask_manual (maintenance handbook search)
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

# full text pipeline: VAD -> STT -> LLM + tools -> answer
ollama pull qwen2.5:3b                              # local LLM, free (https://ollama.com)
python scripts/run_file.py eval/samples
python scripts/run_file.py eval/samples --llm claude   # optional: Claude API, key in .env
python scripts/fetch_datasets.py                  # free eval datasets (FLEURS, AI4I 2020), see DATASETS.md
pytest
```

## Repo structure

```
pipeline/   vad, stt, llm, tts modules + latency timing
functions/  callable tools + mock shop-floor data + maintenance manual
server/     push-to-talk app
eval/       test recordings, WER + latency scripts
results/    latency tables and charts
scripts/    CLI entry points
```
