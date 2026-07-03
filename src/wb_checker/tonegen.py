"""Generate dual-tone (1 kHz + 6 kHz) probe files at 16 kHz."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
LOW_HZ = 1000.0
HIGH_HZ = 6000.0


@dataclass(frozen=True, slots=True)
class ToneSpec:
    """Parameters of the probe signal."""

    duration_s: float = 5.0
    low_hz: float = LOW_HZ
    high_hz: float = HIGH_HZ
    gain_db: float = -6.0
    sample_rate: int = SAMPLE_RATE


def synth_dual_tone(spec: ToneSpec = ToneSpec()) -> np.ndarray:
    """Return int16 PCM samples of the dual-tone probe."""
    n = int(spec.duration_s * spec.sample_rate)
    t = np.arange(n) / spec.sample_rate
    sig = (np.sin(2 * np.pi * spec.low_hz * t)
           + np.sin(2 * np.pi * spec.high_hz * t))
    # Normalize sum of two sines, then apply headroom gain.
    sig *= (10 ** (spec.gain_db / 20)) / 2.0
    # 10 ms raised-cosine fade in/out avoids click transients.
    fade = int(0.010 * spec.sample_rate)
    ramp = 0.5 * (1 - np.cos(np.pi * np.arange(fade) / fade))
    sig[:fade] *= ramp
    sig[-fade:] *= ramp[::-1]
    return (sig * 32767).astype(np.int16)


def write_sln16(samples: np.ndarray, path: Path) -> None:
    """Write raw signed-linear 16 kHz mono (Asterisk .sln16)."""
    path.write_bytes(samples.tobytes())


def write_wav(samples: np.ndarray, path: Path,
              sample_rate: int = SAMPLE_RATE) -> None:
    """Write 16-bit mono WAV."""
    # wave.open("wb") returns Wave_write; pylint infers Wave_read
    # pylint: disable=no-member
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        f.writeframes(samples.tobytes())


def generate(out_dir: Path, basename: str = "hdtest",
             spec: ToneSpec = ToneSpec()) -> list[Path]:
    """Generate .sln16 and .wav probe files, return written paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    samples = synth_dual_tone(spec)
    sln = out_dir / f"{basename}.sln16"
    wav = out_dir / f"{basename}.wav"
    write_sln16(samples, sln)
    write_wav(samples, wav, spec.sample_rate)
    return [sln, wav]
