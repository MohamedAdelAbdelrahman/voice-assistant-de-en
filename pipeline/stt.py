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

    try:
        with wave.open(str(path), "rb") as w:
            sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(w.getnframes())
        if width != 2:
            raise ValueError(f"{path.name}: only 16-bit PCM WAV supported, got {8 * width}-bit")
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except wave.Error:
        # stdlib wave rejects IEEE-float WAV (format 3), which FLEURS uses
        audio, sr, ch = _read_float_wav(path)

    if ch > 1:
        audio = audio.reshape(-1, ch).mean(axis=1)
    if sr != SAMPLE_RATE:
        n_out = int(round(len(audio) * SAMPLE_RATE / sr))
        audio = np.interp(
            np.linspace(0, len(audio) - 1, n_out), np.arange(len(audio)), audio
        ).astype(np.float32)
    return audio


def _read_float_wav(path: Path) -> tuple[np.ndarray, int, int]:
    """Minimal RIFF parser for 32-bit IEEE-float WAV. Returns (samples, rate, channels)."""
    data = path.read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError(f"{path.name}: not a WAV file")
    pos, fmt, samples = 12, None, None
    while pos + 8 <= len(data):
        cid, size = data[pos : pos + 4], int.from_bytes(data[pos + 4 : pos + 8], "little")
        body = data[pos + 8 : pos + 8 + size]
        if cid == b"fmt ":
            tag, ch, sr = (int.from_bytes(body[0:2], "little"), int.from_bytes(body[2:4], "little"),
                           int.from_bytes(body[4:8], "little"))
            bits = int.from_bytes(body[14:16], "little")
            if tag == 0xFFFE and len(body) >= 26:  # WAVE_FORMAT_EXTENSIBLE: real tag in sub-format
                tag = int.from_bytes(body[24:26], "little")
            fmt = (tag, ch, sr, bits)
        elif cid == b"data":
            samples = body
        pos += 8 + size + (size & 1)
    if fmt is None or samples is None:
        raise ValueError(f"{path.name}: missing fmt or data chunk")
    tag, ch, sr, bits = fmt
    if tag != 3 or bits != 32:
        raise ValueError(f"{path.name}: unsupported WAV format tag={tag} bits={bits}")
    return np.frombuffer(samples, dtype="<f4").astype(np.float32), sr, ch


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
