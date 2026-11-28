# Real-time Voice Assistant (DE + EN)

[![tests](https://github.com/MohamedAdelAbdelrahman/voice-assistant-de-en/actions/workflows/tests.yml/badge.svg)](https://github.com/MohamedAdelAbdelrahman/voice-assistant-de-en/actions/workflows/tests.yml)

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
python scripts/run_file.py eval/samples --tts-out results/answers   # also speak the answers (Piper, voices download on first use)
python scripts/fetch_datasets.py                  # free eval datasets (FLEURS, AI4I 2020), see DATASETS.md
pytest
```

## Maintenance handbook (`ask_manual`)

How-to and safety questions ("Was bedeutet E-204?", "What do I have to do before I open a machine?") are answered from a short fictional DE/EN handbook in `functions/data/manual/`, one section per alarm code or procedure. `functions/manual.py` searches it with BM25: no extra model, under 1 ms per query, and it copes with STT spellings of alarm codes ("E 204", "E204") and German compounds. Answers name their handbook section.

qwen2.5:3b often answered safety questions from general knowledge instead of calling the tool, even with explicit prompt rules (7/10 correct on a text check). The Ollama backend therefore runs the handbook search up front when the question is clearly a how-to or safety question. This brought the check to 10/10 and saves one LLM round trip.

## Licences

Code dependencies include Piper TTS (`piper-tts`, GPL-3.0), used unmodified. The voices are `de_DE-thorsten-medium` (CC0) and `en_US-ljspeech-medium` (public domain); datasets and their licences are listed in [DATASETS.md](DATASETS.md).

## Repo structure

```
pipeline/   vad, stt, llm, tts modules + latency timing
functions/  callable tools + mock shop-floor data + maintenance manual
server/     push-to-talk app
eval/       test recordings, WER + latency scripts
results/    latency tables and charts
scripts/    CLI entry points
```
