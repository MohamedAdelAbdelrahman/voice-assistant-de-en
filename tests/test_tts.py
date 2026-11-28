"""TTS tests with a fake Piper voice: no model download, runs in CI."""
import wave
from types import SimpleNamespace as NS

import numpy as np
import pytest

from pipeline.tts import Speech, TextToSpeech, save_wav


class FakeVoice:
    def __init__(self, rate=22050):
        self.config = NS(sample_rate=rate)
        self.calls = []

    def synthesize(self, text, config=None):
        self.calls.append((text, config))
        # 10 samples per character, split over two chunks like Piper does per sentence
        n = 10 * len(text)
        yield NS(audio_int16_bytes=np.ones(n // 2, dtype=np.int16).tobytes())
        yield NS(audio_int16_bytes=np.ones(n - n // 2, dtype=np.int16).tobytes())


@pytest.fixture
def tts():
    loaded = []

    def loader(name, model_dir):
        loaded.append(name)
        return FakeVoice()

    t = TextToSpeech(loader=loader)
    t.loaded = loaded
    return t


def test_loads_each_voice_once(tts):
    assert tts.loaded == ["de_DE-thorsten-medium", "en_US-ljspeech-medium"]
    tts.synthesize("Hallo", "de")
    tts.synthesize("Hallo", "de")
    assert len(tts.loaded) == 2


def test_voice_chosen_by_language(tts):
    tts.synthesize("Linie 2 läuft.", "de")
    tts.synthesize("Line 2 is running.", "en")
    assert tts.voices["de"].calls[0][0] == "Linie 2 läuft."
    assert tts.voices["en"].calls[0][0] == "Line 2 is running."


def test_unknown_language_falls_back_to_english(tts):
    s = tts.synthesize("Bonjour", "fr")
    assert s.language == "en" and tts.voices["en"].calls


def test_audio_joined_from_chunks(tts):
    s = tts.synthesize("abcde", "en")
    assert s.audio.dtype == np.int16 and len(s.audio) == 50
    assert s.sample_rate == 22050 and s.ms >= 0
    assert s.duration_s == pytest.approx(50 / 22050)


def test_empty_text_gives_no_audio(tts):
    s = tts.synthesize("   ", "de")
    assert len(s.audio) == 0 and not tts.voices["de"].calls


def test_warmup_uses_every_voice(tts):
    tts.warmup()
    assert tts.voices["de"].calls and tts.voices["en"].calls


def test_length_scale_is_passed(monkeypatch):
    t = TextToSpeech(loader=lambda n, d: FakeVoice(), length_scale=1.2)
    t.synthesize("Hi", "en")
    assert t.voices["en"].calls[0][1].length_scale == 1.2


def test_save_wav(tmp_path):
    a = Speech(np.arange(100, dtype=np.int16), 22050, "de", 1.0)
    b = Speech(np.arange(50, dtype=np.int16), 22050, "de", 1.0)
    path = save_wav([a, b], tmp_path / "out" / "answer.wav")
    with wave.open(str(path)) as w:
        assert w.getframerate() == 22050 and w.getnchannels() == 1 and w.getsampwidth() == 2
        assert w.getnframes() == 150


def test_save_wav_rejects_mixed_rates(tmp_path):
    a = Speech(np.zeros(10, dtype=np.int16), 22050, "de", 1.0)
    b = Speech(np.zeros(10, dtype=np.int16), 16000, "en", 1.0)
    with pytest.raises(ValueError):
        save_wav([a, b], tmp_path / "x.wav")
    with pytest.raises(ValueError):
        save_wav([], tmp_path / "x.wav")
