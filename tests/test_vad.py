from pathlib import Path

import numpy as np
import pytest

from pipeline.stt import load_audio
from pipeline.vad import SAMPLE_RATE, EndOfSpeechDetector, VoiceActivityDetector

SAMPLE = Path(__file__).parents[1] / "eval" / "samples" / "en_01_line_status.wav"


@pytest.fixture(scope="module")
def vad():
    return VoiceActivityDetector()


@pytest.fixture(scope="module")
def padded():
    """1 s silence + speech + 2 s silence."""
    speech = load_audio(SAMPLE)
    sil = np.zeros(SAMPLE_RATE, dtype=np.float32)
    return np.concatenate([sil, speech, sil, sil]), len(speech) / SAMPLE_RATE


def test_silence_has_no_speech(vad):
    r = vad.trim(np.zeros(2 * SAMPLE_RATE, dtype=np.float32))
    assert not r.has_speech and len(r.audio) == 0


def test_trim_removes_added_silence(vad, padded):
    audio, speech_len = padded
    r = vad.trim(audio)
    assert r.has_speech
    assert 1.0 <= r.start_s <= 1.0 + speech_len
    assert r.end_s <= 1.0 + speech_len + 0.1
    assert len(r.audio) / SAMPLE_RATE < speech_len + 0.5  # the 3 s of padding are gone


@pytest.mark.parametrize("silence_ms", [300, 700])
def test_end_of_speech_fires_after_silence(vad, padded, silence_ms):
    audio, _ = padded
    eos = EndOfSpeechDetector(silence_ms=silence_ms, model=vad.model)
    for i in range(0, len(audio), 320):  # 20 ms chunks, like a mic callback
        if eos.feed(audio[i : i + 320]):
            break
    assert eos.ended
    delay = eos.detected_at_s - eos.speech_end_s
    assert abs(delay - silence_ms / 1000) < 0.05


def test_end_of_speech_never_fires_on_silence(vad):
    eos = EndOfSpeechDetector(silence_ms=300, model=vad.model)
    assert not eos.feed(np.zeros(3 * SAMPLE_RATE, dtype=np.float32))
    assert eos.speech_start_s is None
