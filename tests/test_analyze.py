"""Tests for recording analysis: HD vs narrowband verdicts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from wb_checker.analyze import analyze, read_audio
from wb_checker.tonegen import (
    SAMPLE_RATE, ToneSpec, synth_dual_tone, write_sln16, write_wav)


def _lowpass_3400(samples: np.ndarray) -> np.ndarray:
    """Crude narrowband simulation: zero FFT bins above 3.4 kHz."""
    spec = np.fft.rfft(samples.astype(np.float64))
    freqs = np.fft.rfftfreq(len(samples), 1 / SAMPLE_RATE)
    spec[freqs > 3400] = 0
    out = np.fft.irfft(spec, len(samples))
    return out.astype(np.int16)


def test_clean_path_is_hd(tmp_path: Path) -> None:
    """Unmodified probe recording verdicts HD."""
    wav = tmp_path / "rec.wav"
    write_wav(synth_dual_tone(ToneSpec(duration_s=2.0)), wav)
    v = analyze(wav)
    assert v.is_hd
    assert v.ratio_db > -6


def test_transcoded_path_is_narrowband(tmp_path: Path) -> None:
    """Lowpassed (fake ulaw hop) recording verdicts narrowband."""
    wav = tmp_path / "rec.wav"
    write_wav(_lowpass_3400(
        synth_dual_tone(ToneSpec(duration_s=2.0))), wav)
    v = analyze(wav)
    assert not v.is_hd
    assert v.ratio_db < -35


def test_sln16_roundtrip(tmp_path: Path) -> None:
    """Raw .sln16 files are readable and analyzable."""
    sln = tmp_path / "rec.sln16"
    write_sln16(synth_dual_tone(ToneSpec(duration_s=2.0)), sln)
    samples, rate = read_audio(sln)
    assert rate == SAMPLE_RATE
    assert len(samples) == 2 * SAMPLE_RATE
    assert analyze(sln).is_hd


def test_8k_recording_rejected(tmp_path: Path) -> None:
    """Recording at 8 kHz cannot prove HD; must raise."""
    wav = tmp_path / "rec.wav"
    s = synth_dual_tone(ToneSpec(duration_s=1.0))[::2]
    write_wav(s, wav, sample_rate=8000)
    with pytest.raises(ValueError, match="sample rate"):
        analyze(wav)


def test_silence_rejected(tmp_path: Path) -> None:
    """All-silent recording must raise, not verdict."""
    wav = tmp_path / "rec.wav"
    write_wav(np.zeros(SAMPLE_RATE, dtype=np.int16), wav)
    with pytest.raises(ValueError, match="no usable signal"):
        analyze(wav)
