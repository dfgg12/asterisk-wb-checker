"""Tests for probe tone generation."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from wb_checker.tonegen import (
    SAMPLE_RATE, ToneSpec, generate, synth_dual_tone)


def test_synth_length_and_range() -> None:
    """Samples match duration, stay within int16 and headroom."""
    spec = ToneSpec(duration_s=2.0)
    s = synth_dual_tone(spec)
    assert len(s) == 2 * SAMPLE_RATE
    assert s.dtype == np.int16
    assert np.abs(s).max() < 32768 * 0.6


def test_spectrum_has_both_tones() -> None:
    """FFT peaks appear at 1 kHz and 6 kHz."""
    s = synth_dual_tone(ToneSpec(duration_s=1.0)).astype(float)
    spec = np.abs(np.fft.rfft(s))
    freqs = np.fft.rfftfreq(len(s), 1 / SAMPLE_RATE)
    peaks = freqs[np.argsort(spec)[-2:]]
    assert sorted(round(p) for p in peaks) == [1000, 6000]


def test_generate_writes_files(tmp_path: Path) -> None:
    """Both .sln16 and .wav are written and sized sanely."""
    paths = generate(tmp_path, spec=ToneSpec(duration_s=1.0))
    assert [p.suffix for p in paths] == [".sln16", ".wav"]
    assert paths[0].stat().st_size == 2 * SAMPLE_RATE
    assert paths[1].stat().st_size > paths[0].stat().st_size
