"""Speech-to-text with faster-whisper, restricted to German and English.

The model is loaded once (constructor) and warmed up, never per request.
"""
from __future__ import annotations

import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel, decode_audio

SAMPLE_RATE = 16_000


@dataclass
class Transcript:
    text: str
    language: str
    language_prob: float
    audio_s: float
    segments: list[dict] = field(default_factory=list)


def load_audio(path: str | Path) -> np.ndarray:
    """Load an audio file as 16 kHz mono float32.

    PCM WAV is read with the stdlib (fast, no PyAV dependency); other formats
    fall back to faster-whisper's PyAV decoder.
    """
    path = Path(path)
    if path.suffix.lower() != ".wav":
        return decode_audio(str(path), sampling_rate=SAMPLE_RATE)

    with wave.open(str(path), "rb") as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path.name}: only 16-bit PCM WAV supported, got {8 * width}-bit")

    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    if sr != SAMPLE_RATE:
        n_out = int(round(len(audio) * SAMPLE_RATE / sr))
        audio = np.interp(
            np.linspace(0, len(audio) - 1, n_out), np.arange(len(audio)), audio
        ).astype(np.float32)
    return audio


class SpeechToText:
    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        languages: tuple[str, ...] = ("de", "en"),
        beam_size: int = 5,
        initial_prompt: str | None = None,
    ) -> None:
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self.languages = languages
        self.beam_size = beam_size
        self.initial_prompt = initial_prompt

    def warmup(self) -> None:
        """Run one dummy pass so the first real request isn't slowed by lazy init."""
        self.transcribe(np.zeros(SAMPLE_RATE, dtype=np.float32), language="en")

    def transcribe(self, audio: np.ndarray, language: str | None = None) -> Transcript:
        text, info, segs = self._run(audio, language)

        # Whisper knows ~100 languages; on the shop floor we only accept DE/EN.
        # If detection picks something else, re-run with the most likely allowed one.
        if language is None and info.language not in self.languages:
            probs = dict(info.all_language_probs or [])
            best = max(self.languages, key=lambda lang: probs.get(lang, 0.0))
            text, info, segs = self._run(audio, best)
            info_prob = probs.get(best, 0.0)
        else:
            info_prob = info.language_probability

        return Transcript(
            text=text,
            language=info.language,
            language_prob=round(float(info_prob), 3),
            audio_s=round(len(audio) / SAMPLE_RATE, 2),
            segments=segs,
        )

    def _run(self, audio: np.ndarray, language: str | None):
        segments, info = self.model.transcribe(
            audio,
            language=language,
            beam_size=self.beam_size,
            initial_prompt=self.initial_prompt,
            condition_on_previous_text=False,
        )
        segs = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]
        text = " ".join(s["text"] for s in segs).strip()
        return text, info, segs
