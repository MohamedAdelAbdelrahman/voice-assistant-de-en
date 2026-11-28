"""Text-to-speech with Piper: one German and one English voice, picked by language.

Both voices are loaded once and warmed up at startup, never per request: the
first synthesis after loading takes ~3.5 s (onnxruntime graph setup), later
ones run at ~0.05x real time on CPU (5.6 s of speech in ~0.25 s).

Voices (downloaded to ``models/piper/`` on first use, git-ignored):
* ``de_DE-thorsten-medium``: Thorsten-Voice dataset, CC0
* ``en_US-ljspeech-medium``: LJ Speech dataset, public domain
``en_US-lessac`` was not used: its model card links to the Blizzard 2013 licence
instead of stating one, so commercial use is unclear.
"""
from __future__ import annotations

import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

VOICES = {"de": "de_DE-thorsten-medium", "en": "en_US-ljspeech-medium"}
MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "piper"
WARMUP_TEXT = {"de": "Hallo.", "en": "Hello."}


@dataclass
class Speech:
    audio: np.ndarray  # int16 mono
    sample_rate: int
    language: str
    ms: float  # synthesis time

    @property
    def duration_s(self) -> float:
        return len(self.audio) / self.sample_rate


def _load_piper(name: str, model_dir: Path) -> Any:
    from piper import PiperVoice
    from piper.download_voices import download_voice

    path = model_dir / f"{name}.onnx"
    if not path.exists() or not path.with_suffix(".onnx.json").exists():
        model_dir.mkdir(parents=True, exist_ok=True)
        download_voice(name, model_dir)
    return PiperVoice.load(path)


class TextToSpeech:
    def __init__(
        self,
        voices: dict[str, str] | None = None,
        model_dir: Path = MODEL_DIR,
        length_scale: float | None = None,  # >1 speaks slower; None = voice default
        loader: Callable[[str, Path], Any] = _load_piper,
    ) -> None:
        self.voices = {lang: loader(name, model_dir) for lang, name in (voices or VOICES).items()}
        self.names = dict(voices or VOICES)
        self.length_scale = length_scale

    def warmup(self) -> None:
        for lang in self.voices:
            self.synthesize(WARMUP_TEXT.get(lang, "Hello."), lang)

    def sample_rate(self, language: str) -> int:
        return self._voice(language).config.sample_rate

    def _voice(self, language: str) -> Any:
        return self.voices.get(language) or self.voices["en"]

    def synthesize(self, text: str, language: str) -> Speech:
        """Speak ``text`` with the voice for ``language`` (unknown languages fall back to English)."""
        lang = language if language in self.voices else "en"
        voice = self._voice(lang)
        t = time.perf_counter()
        config = None
        if self.length_scale is not None:
            from piper import SynthesisConfig

            config = SynthesisConfig(length_scale=self.length_scale)
        chunks = [c.audio_int16_bytes for c in voice.synthesize(text, config)] if text.strip() else []
        audio = np.frombuffer(b"".join(chunks), dtype=np.int16)
        ms = round((time.perf_counter() - t) * 1000, 1)
        return Speech(audio=audio, sample_rate=voice.config.sample_rate, language=lang, ms=ms)


def save_wav(speech: Speech | list[Speech], path: str | Path) -> Path:
    """Write one or more Speech pieces (same sample rate) to a 16-bit mono WAV."""
    parts = speech if isinstance(speech, list) else [speech]
    if not parts:
        raise ValueError("nothing to write")
    rate = parts[0].sample_rate
    if any(p.sample_rate != rate for p in parts):
        raise ValueError("all pieces must have the same sample rate")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(p.audio.tobytes() for p in parts))
    return path
