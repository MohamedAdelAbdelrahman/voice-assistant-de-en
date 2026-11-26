"""Voice activity detection with Silero VAD (ONNX, bundled with faster-whisper).

Two uses:

* ``VoiceActivityDetector.trim(audio)`` — offline: cut leading/trailing silence
  from a recorded utterance before it goes to STT (less audio = faster STT).
* ``EndOfSpeechDetector`` — streaming: feed 32 ms frames as they arrive and get
  told the moment the speaker has stopped (trailing silence ≥ threshold). That
  moment is t=0 for the "first audio ≤ 2 s" latency target.

Silero runs on 512-sample frames (32 ms at 16 kHz) with 64 samples of context
from the previous frame and a recurrent state (h, c) carried across frames.
Using onnxruntime directly avoids a torch dependency.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import onnxruntime
from faster_whisper.utils import get_assets_path

SAMPLE_RATE = 16_000
FRAME = 512  # samples per Silero window (32 ms)
CONTEXT = 64  # samples of left context the model expects
FRAME_S = FRAME / SAMPLE_RATE


@dataclass
class VadResult:
    audio: np.ndarray  # trimmed audio (speech + padding)
    start_s: float  # speech start in the original audio
    end_s: float  # speech end in the original audio
    original_s: float

    @property
    def speech_s(self) -> float:
        return round(self.end_s - self.start_s, 3)

    @property
    def has_speech(self) -> bool:
        return self.end_s > self.start_s


class SileroModel:
    """Thin stateful wrapper around the Silero v6 ONNX graph."""

    def __init__(self, path: str | None = None, threads: int = 1) -> None:
        path = path or os.path.join(get_assets_path(), "silero_vad_v6.onnx")
        opts = onnxruntime.SessionOptions()
        opts.inter_op_num_threads = 1
        opts.intra_op_num_threads = threads
        opts.log_severity_level = 4
        self.session = onnxruntime.InferenceSession(
            path, providers=["CPUExecutionProvider"], sess_options=opts
        )
        self.reset()

    def reset(self) -> None:
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros(CONTEXT, dtype=np.float32)

    def frame_prob(self, frame: np.ndarray) -> float:
        """Speech probability for one 512-sample frame; advances the state."""
        x = np.concatenate([self.context, frame.astype(np.float32)])[None, :]
        out, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
        self.context = frame[-CONTEXT:].astype(np.float32)
        return float(np.asarray(out).reshape(-1)[0])

    def probs(self, audio: np.ndarray) -> np.ndarray:
        """Speech probability per 32 ms frame for a whole clip (fresh state)."""
        self.reset()
        pad = (-len(audio)) % FRAME
        audio = np.pad(audio.astype(np.float32), (0, pad))
        return np.array([self.frame_prob(f) for f in audio.reshape(-1, FRAME)])


class VoiceActivityDetector:
    def __init__(
        self,
        threshold: float = 0.5,
        min_speech_ms: int = 150,
        pad_ms: int = 200,
    ) -> None:
        self.model = SileroModel()
        self.threshold = threshold
        self.neg_threshold = max(threshold - 0.15, 0.01)  # hysteresis, as in Silero
        self.min_speech_frames = max(1, round(min_speech_ms / 1000 / FRAME_S))
        self.pad = int(pad_ms / 1000 * SAMPLE_RATE)

    def warmup(self) -> None:
        self.model.probs(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))

    def trim(self, audio: np.ndarray) -> VadResult:
        """Keep everything from the first to the last speech frame (plus padding).

        Pauses *inside* the utterance are kept on purpose: cutting them would
        glue words together and hurt WER for little speed gain.
        """
        n = len(audio)
        speech = self._speech_mask(self.model.probs(audio))
        idx = np.flatnonzero(speech)
        if len(idx) == 0:
            return VadResult(audio[:0], 0.0, 0.0, round(n / SAMPLE_RATE, 3))

        start = idx[0] * FRAME
        end = min(n, (idx[-1] + 1) * FRAME)
        lo, hi = max(0, start - self.pad), min(n, end + self.pad)
        return VadResult(
            audio=audio[lo:hi],
            start_s=round(start / SAMPLE_RATE, 3),
            end_s=round(end / SAMPLE_RATE, 3),
            original_s=round(n / SAMPLE_RATE, 3),
        )

    def _speech_mask(self, probs: np.ndarray) -> np.ndarray:
        """Frame-level speech mask with hysteresis; drops blips shorter than min_speech."""
        mask = np.zeros(len(probs), dtype=bool)
        on = False
        for i, p in enumerate(probs):
            if not on and p >= self.threshold:
                on = True
            elif on and p < self.neg_threshold:
                on = False
            mask[i] = on

        # remove runs shorter than min_speech_frames (clicks, coughs)
        i = 0
        while i < len(mask):
            if mask[i]:
                j = i
                while j < len(mask) and mask[j]:
                    j += 1
                if j - i < self.min_speech_frames:
                    mask[i:j] = False
                i = j
            else:
                i += 1
        return mask


class EndOfSpeechDetector:
    """Streaming endpointing: speech started, then ``silence_ms`` of non-speech.

    ``silence_ms`` is the main latency/robustness knob: every millisecond here
    is added to the response time, but too low and a short pause mid-sentence
    ("Linie ... drei") ends the turn early. Tuned on Day 8.
    """

    def __init__(
        self,
        silence_ms: int = 500,
        threshold: float = 0.5,
        min_speech_ms: int = 150,
        model: SileroModel | None = None,
    ) -> None:
        self.model = model or SileroModel()
        self.threshold = threshold
        self.neg_threshold = max(threshold - 0.15, 0.01)
        self.silence_frames = max(1, round(silence_ms / 1000 / FRAME_S))
        self.min_speech_frames = max(1, round(min_speech_ms / 1000 / FRAME_S))
        self.reset()

    def reset(self) -> None:
        self.model.reset()
        self._buf = np.zeros(0, dtype=np.float32)
        self.frames = 0
        self.speech_frames = 0
        self.silent_run = 0
        self.speech_start_s: float | None = None
        self.speech_end_s: float | None = None
        self.ended = False

    @property
    def in_speech(self) -> bool:
        return self.speech_frames >= self.min_speech_frames

    def feed(self, chunk: np.ndarray) -> bool:
        """Feed any number of samples. Returns True once end of speech is detected."""
        if self.ended:
            return True
        self._buf = np.concatenate([self._buf, chunk.astype(np.float32)])
        while len(self._buf) >= FRAME and not self.ended:
            frame, self._buf = self._buf[:FRAME], self._buf[FRAME:]
            self._step(self.model.frame_prob(frame))
        return self.ended

    def _step(self, p: float) -> None:
        t = self.frames * FRAME_S
        self.frames += 1
        if p >= self.threshold:
            if self.speech_frames == 0:
                self.speech_start_s = round(t, 3)
            self.speech_frames += 1
            self.silent_run = 0
            self.speech_end_s = round(t + FRAME_S, 3)
        elif p < self.neg_threshold or self.silent_run > 0:
            if self.in_speech:
                self.silent_run += 1
                if self.silent_run >= self.silence_frames:
                    self.ended = True
            elif self.speech_frames:
                # too short to count as speech (click/cough): start over
                self.speech_frames = 0
                self.speech_start_s = None

    @property
    def detected_at_s(self) -> float | None:
        """Audio time at which the end of speech was declared."""
        return round(self.frames * FRAME_S, 3) if self.ended else None
