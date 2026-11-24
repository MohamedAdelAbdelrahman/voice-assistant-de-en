# Roadmap: Real-time Voice Assistant (DE + EN)

A voice assistant for the shop floor. Ask a question in German or English and get a spoken answer back fast. Response time is measured and optimized one stage at a time.

**Pipeline:** Silero VAD → faster-whisper (STT + language detection) → LLM with function calling (`get_line_status`, `create_ticket`, `list_alarms`, plus a bridge to my LangGraph agent) → Piper TTS, with sentence-level streaming

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

### Day 2 · Thu 2026-11-26 · VAD + tools (3 h) ⬜
- [ ] `pipeline/vad.py`: use Silero VAD to trim leading and trailing silence and detect when speech ends
- [ ] Chain VAD → STT on files and log both timings
- [ ] `functions/`: mock shop-floor data (lines 1–5, machines 1–12, alarms, tickets) as JSON
- [ ] Implement `get_line_status(line_id)`, `list_alarms(line_id?, severity?)`, `create_ticket(machine_id, description, priority)` with JSON schemas
- [ ] Unit tests for the tools
- **Commit:** `feat: Silero VAD + shop-floor tools with schemas`

### Day 3 · Fri 2026-11-27 · LLM function calling (3 h) ⬜ → **M1**
- [ ] `pipeline/llm.py`: LLM client (Ollama or API) with tool calling and a streaming response
- [ ] System prompt: answer in the detected language, keep answers short and easy to speak
- [ ] Tool loop: the LLM calls a tool, gets the result, and writes the final answer
- [ ] `scripts/run_file.py`: takes a WAV and prints the transcript, the tool call and the answer
- **Commit:** `feat: LLM function calling, end-to-end text pipeline on audio files`

### Day 4 · Mon 2026-11-30 · Agent bridge + TTS (3 h) ⬜
- [ ] `functions/agent_bridge.py`: an `ask_agent(question)` tool that sends complex questions to the Project B LangGraph agent (HTTP or import), with a timeout and a fallback answer
- [ ] Routing rules in the prompt: simple commands go to the direct tools, open questions go to the agent
- [ ] `pipeline/tts.py`: Piper with one German voice (e.g. `de_DE-thorsten`) and one English voice (e.g. `en_US-lessac`), loaded once, voice chosen by language
- **Commit:** `feat: LangGraph agent bridge + Piper TTS (DE/EN)`

### Day 5 · Tue 2026-12-01 · Streaming (3 h) ⬜ → **M2**
- [ ] Split the LLM token stream into sentences, keeping numbers and abbreviations like "z. B." or "Nr. 7" intact
- [ ] Producer/consumer queue: each sentence goes to Piper, then to an audio output or WAV writer, as soon as it is complete
- [ ] Log the first-token and first-audio timestamps
- [ ] Compare streaming and non-streaming first-audio time on 5 files
- **Commit:** `feat: sentence-level streaming LLM → TTS`
- **Tag:** `v0.1`

---

## Week 2: Measure, optimize, ship

### Day 6 · Wed 2026-12-02 · Test dataset (3 h) ⬜
- [ ] Write 30 DE and 30 EN test sentences that include machine names, line numbers, numbers and alarm codes
- [ ] Record them and save them to `eval/audio/{de,en}/NN.wav`
- [ ] `eval/dataset.jsonl`: for each sentence, the reference transcript, the expected function and the expected arguments
- **Commit:** `eval: 60 recorded test sentences with references and expected calls`

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
- [ ] Record a 1–2 min demo video with one DE and one EN query, a tool call, an agent question and the confirmation step
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
| Agent from Project B is slow or unavailable | Timeout plus a spoken fallback; report agent latency separately |
| Optimizing the wrong stage | Measure first on Day 7 and fix the slowest stage first |
| Misrecognized commands trigger actions | Confirm before any action that changes something |
| Falling behind schedule | Nice-to-haves are cut first; the must-haves are done by Day 9 |
