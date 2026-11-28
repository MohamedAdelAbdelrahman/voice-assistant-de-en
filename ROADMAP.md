# Roadmap: Real-time Voice Assistant (DE + EN)

A voice assistant for the shop floor. Ask a question in German or English and get a spoken answer back fast. Response time is measured and optimized one stage at a time.

**Pipeline:** Silero VAD → faster-whisper (STT + language detection) → LLM with function calling (`get_line_status`, `create_ticket`, `list_alarms`, `ask_manual` for open how-to questions, and `get_machine_telemetry`) → Piper TTS, with sentence-level streaming

**Time budget:** 2 weeks · 10 working days · ~3 h/day · ~30 h total
**Timeline:** Wed 2026-11-25 → Tue 2026-12-08
**Target:** first audio within **2.0 s (p95)** after the speaker stops talking, on CPU

Legend: ✅ done · 🔄 in progress · ⬜ not started

---

## Milestones

| Milestone | Date | Done when |
|---|---|---|
| **M1: Offline pipeline** | Fri 2026-11-27 (Day 3) | A WAV file goes in, the right function is called, and a text answer comes out in the same language |
| **M2: Spoken + streaming** | Tue 2026-12-01 (Day 5) | A WAV file goes in and spoken audio comes out, starting on the first sentence. Tag `v0.1` |
| **M3: Evaluated** | Thu 2026-12-03 (Day 7) | Baseline WER, function-call accuracy and latency p50/p95 are in `results/` |
| **M4: Optimized + live** | Mon 2026-12-07 (Day 9) | Before/after latency table is filled in and push-to-talk works from the microphone |
| **M5: Release** | Tue 2026-12-08 (Day 10) | README, charts and demo video are done. Tag `v1.0` |

---

## Week 1: Build the pipeline on recorded audio

### Day 1 · Wed 2026-11-25 · Setup + STT on files (3 h) ✅
- [x] Repo skeleton: `pipeline/`, `functions/`, `server/`, `eval/`, `results/`, `pyproject.toml` / `requirements.txt`, `.gitignore`
- [x] Record or collect 5–10 sample WAVs (16 kHz mono), both DE and EN
- [x] `pipeline/stt.py`: load faster-whisper **once** at startup, warm it up, transcribe a file, return the text and the detected language
- [x] `pipeline/timing.py`: a small `Timer` context manager that writes one JSONL record per stage
- **Commit:** `feat: project skeleton + faster-whisper STT with language detection`
- **Note:** first measurement with `small` int8 on CPU: STT takes about 4–6 s per short utterance. That alone is over the 2 s target, so STT is the first thing to optimize on Day 8.

### Day 2 · Thu 2026-11-26 · VAD + tools (3 h) ✅
- [x] `pipeline/vad.py`: use Silero VAD to trim leading and trailing silence and detect when speech ends
- [x] Chain VAD → STT on files and log both timings
- [x] `functions/`: mock shop-floor data (lines 1–5, machines 1–12, alarms, tickets) as JSON
- [x] Implement `get_line_status(line_id)`, `list_alarms(line_id?, severity?)`, `create_ticket(machine_id, description, priority)` with JSON schemas
- [x] Unit tests for the tools
- **Commit:** `feat: Silero VAD + shop-floor tools with schemas`
- **Note:** Silero v6 runs via onnxruntime using the model bundled with faster-whisper, so there is no torch dependency. VAD takes about 10–20 ms per utterance. End of speech is detected `silence_ms` (default 500 ms) after the last speech frame. That wait counts directly toward the 2 s budget, so it gets tuned on Day 8. Trimming silence barely changes STT time because Whisper pads every input to a 30 s window.

### Day 3 · Fri 2026-11-27 · LLM function calling (3 h) ✅ → **M1 reached**
- [x] `pipeline/llm.py`: LLM client (Ollama or API) with tool calling and a streaming response
- [x] System prompt: answer in the detected language, keep answers short and easy to speak
- [x] Tool loop: the LLM calls a tool, gets the result, and writes the final answer
- [x] `scripts/run_file.py`: takes a WAV and prints the transcript, the tool call and the answer
- **Commit:** `feat: LLM function calling, end-to-end text pipeline on audio files`
- **Decision:** the LLM runs **locally via Ollama** (free, offline) on the laptop GPU (GTX 1650, 4 GB). The Claude API backend is kept as an option (`--llm claude`) for a later cloud-vs-local comparison.
- **Model choice** (6 DE/EN questions, text only):

  | Model | Correct tool | Runs on | Notes |
  |---|---|---|---|
  | **qwen2.5:3b** | **6/6** | 100% GPU | chosen; 2.5–5.4 s per turn |
  | qwen3:4b-instruct | 1/6 | 68% GPU | answered from imagination instead of calling tools |
  | qwen3:4b | n/a | 66% GPU | writes its reasoning into the answer despite `think=False`, ~6 min per turn |

- **Open issues for Day 5 and Day 8:**
  - Answers are sometimes too long or use list formatting, which doesn't work for speech.
  - One arithmetic slip (52 out of a target of 50 was called "92%").
  - When the user gave no description, the model invented one for a ticket. The Day 9 confirmation step guards against this.
  - First LLM token takes 1.7–3.5 s because the tool round runs before any text. STT (~3.8 s) is still the largest stage.

### Day 4 · Mon 2026-11-30 · Maintenance manual Q&A + TTS (3 h) ✅
- [x] `functions/data/manual/`: a short DE/EN maintenance handbook: what each alarm code means, the fix steps, safety rules (e.g. lockout before opening a machine)
- [x] `functions/manual.py`: an `ask_manual(question)` tool that finds the most relevant handbook sections with local keyword/BM25 search (free, no extra model) and returns them with their source
- [x] Routing rules in the prompt: status/alarms/tickets go to the direct tools; "how do I…", "what does E-204 mean", safety questions go to `ask_manual`; the answer cites only the handbook
- [x] `pipeline/tts.py`: Piper with one German voice (`de_DE-thorsten`, CC0) and one English voice (check the licence first: `en_US-lessac` is reported as non-commercial), loaded once, voice chosen by language
- [x] CI: GitHub Actions workflow runs `pytest` on every push, with a "tests passing" badge in the README (the tests use fakes, so no models or GPU are needed)
- **Commit:** `feat: maintenance manual Q&A tool + Piper TTS (DE/EN)`
- **Change:** this replaces the earlier plan to bridge to a separate "Project B" LangGraph agent, which doesn't exist.
- **Note:** done on Sat 2026-11-28, ahead of the calendar date.
- **Handbook:** 12 sections (8 alarm codes, LOTO, protective equipment, tool change, who to call), the same IDs in DE and EN. The BM25 search handles STT spellings of codes ("E 204", "E204") and German compounds ("Spindelüberhitzung"), and finds the right section for all 11 test questions in `tests/test_manual.py`.
- **Routing:** with the routing rules in the prompt alone, qwen2.5:3b called the right tool for 7 of 10 text questions. It answered lockout, emergency-stop and injury questions from general knowledge. Two fixes brought it to 10/10:
  - The Ollama backend now runs `ask_manual` before the LLM when the question is clearly a how-to or safety question. A regex catches phrasing like "how do I", "was bedeutet" or "bevor ich". This also saves one LLM round, so the first token comes after ~1.5–1.8 s instead of ~2–3 s.
  - The new prompt block made English answers about line status come out in German. The block is now placed after the answer rules, and the reply language is repeated after every tool result.
- **TTS:** English voice: `en_US-ljspeech-medium` (LJ Speech, public domain). Lessac's model card doesn't state its licence, so it isn't used. Loading takes ~0.8 s per voice. The first synthesis takes ~3.5 s, so both voices are warmed up at startup. After that, Piper synthesizes 9–24 s of audio in 0.4–1.1 s. `run_file.py --tts-out` speaks the whole answer at once; Day 5 streams it sentence by sentence.
- **Open issues for Day 5 and Day 8:**
  - Answers are still too long for speech: up to 24 s of audio, with lists for alarms. For manual questions, the model sometimes reads the whole handbook section out instead of the two or three main steps.
  - STT is still the largest stage at ~5.5 s.
  - The model still invents a ticket description when the user gives none (en_02). The Day 9 confirmation step guards against this.

### Day 5 · Tue 2026-12-01 · Streaming (3 h) ⬜ → **M2**
- [ ] Split the LLM token stream into sentences, keeping numbers and abbreviations like "z. B." or "Nr. 7" intact
- [ ] Producer/consumer queue: each sentence goes to Piper, then to an audio output or WAV writer, as soon as it is complete
- [ ] Log the first-token and first-audio timestamps
- [ ] Compare streaming and non-streaming first-audio time on 5 files
- **Commit:** `feat: sentence-level streaming LLM → TTS`
- **Tag:** `v0.1`

---

## Week 2: Measure, optimize, ship

### Day 6 · Wed 2026-12-02 · Test dataset + telemetry tool (3 h) ⬜
- [ ] `get_machine_telemetry(machine_id)`: live-looking sensor values (air/process temperature, speed, torque, tool wear, failure flags) taken from the AI4I 2020 dataset (see DATASETS.md), with unit tests
- [ ] Write 30 DE and 30 EN test sentences that include machine names, line numbers, numbers and alarm codes, covering all five tools
- [ ] Record them and save them to `eval/audio/{de,en}/NN.wav`
- [ ] `eval/dataset.jsonl`: for each sentence, the reference transcript, the expected function and the expected arguments
- **Commit:** `feat: machine telemetry tool (AI4I 2020) + 60 recorded test sentences`

### Day 7 · Thu 2026-12-03 · Evaluation scripts + baseline (3 h) ⬜ → **M3**
- [ ] `eval/wer.py`: compute WER with `jiwer` and text normalization (case, punctuation, numbers), per language
- [ ] `eval/function_accuracy.py`: score whether the right function was called, whether the arguments match exactly, and whether the language was detected correctly
- [ ] `eval/latency.py`: run every file N times and report p50/p95 for VAD, STT, LLM first token, first audio and total
- [ ] Save the baseline numbers to `results/baseline.md`
- **Commit:** `eval: WER, function-call accuracy, latency p50/p95 baseline`

### Day 8 · Fri 2026-12-04 · Optimization (3 h) ⬜
Optimize the slowest stage first, based on the Day 7 measurements.
- [ ] STT: try a smaller model, `compute_type="int8"`, a lower `beam_size`, and `initial_prompt` with machine vocabulary (this can also lower WER)
- [ ] VAD: tune the end-of-speech silence threshold
- [ ] LLM: shorter prompt, smaller model, `keep_alive`, warm-up call
- [ ] TTS: check the time to first sentence and the Piper settings
- [ ] Re-run the evaluation after each change and keep a before/after row for each one in `results/latency.md`
- **Commit:** `perf: <change> — first audio p95 X.Xs → Y.Ys`

### Day 9 · Mon 2026-12-07 · Live push-to-talk + safety (3 h) ⬜ → **M4**
- [ ] `server/`: Gradio app (or FastAPI + WebSocket) with push-to-talk from the microphone in DE and EN
- [ ] Confirmation step: `create_ticket` asks "Soll ich das Ticket anlegen?" or "Shall I create the ticket?" before running
- [ ] Load and warm up all models once at startup
- **Commit:** `feat: live push-to-talk UI + confirmation before actions`

### Day 10 · Tue 2026-12-08 · Results + release (3 h) ⬜ → **M5**
- [ ] `results/`: latency chart (p50/p95 per stage, before/after), WER table and function-accuracy table
- [ ] README: architecture diagram, quickstart, results tables, whether the target was reached, limitations
- [ ] Record a 1–2 min demo video with one DE and one EN query, a tool call, a manual question and the confirmation step
- **Tag:** `v1.0` and publish a GitHub release
- **Commit:** `docs: README with results + demo video`

---

## Results (filled in as I go)

| Stage | Baseline p50 | Baseline p95 | Optimized p50 | Optimized p95 |
|---|---|---|---|---|
| VAD (end-of-speech) | | | | |
| STT | | | | |
| LLM first token | | | | |
| First audio | | | | |
| **Target: first audio p95 ≤ 2.0 s** | | | | |

| Metric | DE | EN |
|---|---|---|
| Word error rate | | |
| Language detection accuracy | | |
| Function-call accuracy (name + args) | | |

---

## Nice-to-have (only if time remains)
- [ ] Interrupting the assistant while it speaks (barge-in)
- [ ] Wake word
- [ ] Web UI polish

## Risks and mitigations
| Risk | Mitigation |
|---|---|
| Audio device issues on Windows | Build and test on WAV files first, add the microphone only on Day 9 |
| Manual search returns the wrong section | Return the source section with the answer; check manual questions in the Day 7 eval |
| Optimizing the wrong stage | Measure first on Day 7 and fix the slowest stage first |
| Misrecognized commands trigger actions | Confirm before any action that changes something |
| Falling behind schedule | Nice-to-haves are cut first; the must-haves are done by Day 9 |
