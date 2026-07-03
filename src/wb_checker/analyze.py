"""FFT band-energy analysis of recorded probe audio."""

from __future__ import annotations

import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from wb_checker.tonegen import HIGH_HZ, LOW_HZ, SAMPLE_RATE

# High band within 20 dB of low band means wideband survived.
HD_THRESHOLD_DB = -20.0
BAND_WIDTH_HZ = 150.0


@dataclass(frozen=True, slots=True)
class Verdict:
    """Result of one recording analysis."""

    is_hd: bool
    ratio_db: float
    low_db: float
    high_db: float
    noise_db: float
    sample_rate: int

    def summary(self) -> str:
        """One-line human-readable verdict."""
        label = "HD (wideband)" if self.is_hd else "NARROWBAND"
        return (f"{label} ratio={self.ratio_db:.1f} dB "
                f"low={self.low_db:.1f} dB high={self.high_db:.1f} dB "
                f"noise={self.noise_db:.1f} dB fs={self.sample_rate}")


def read_audio(path: Path) -> tuple[np.ndarray, int]:
    """Read WAV or raw .sln16 file, return float samples and rate."""
    if path.suffix in (".sln16", ".sln"):
        rate = SAMPLE_RATE if path.suffix == ".sln16" else 8000
        raw = np.frombuffer(path.read_bytes(), dtype=np.int16)
        return raw.astype(np.float64) / 32768.0, rate
    with wave.open(str(path), "rb") as f:
        if f.getsampwidth() != 2:
            raise ValueError(f"expected 16-bit PCM: {path}")
        rate = f.getframerate()
        raw = np.frombuffer(
            f.readframes(f.getnframes()), dtype=np.int16)
        if f.getnchannels() > 1:
            raw = raw.reshape(-1, f.getnchannels())[:, 0]
    return raw.astype(np.float64) / 32768.0, rate


def band_energy(spec: np.ndarray, freqs: np.ndarray,
                center: float, width: float = BAND_WIDTH_HZ) -> float:
    """Sum spectral magnitude in [center-width, center+width]."""
    mask = (freqs > center - width) & (freqs < center + width)
    return float(spec[mask].sum())


def analyze(path: Path, low_hz: float = LOW_HZ,
            high_hz: float = HIGH_HZ,
            threshold_db: float = HD_THRESHOLD_DB) -> Verdict:
    """Analyze a recording and decide HD vs narrowband."""
    samples, rate = read_audio(path)
    if rate < 2 * high_hz:
        # Recording itself cannot contain the high probe tone.
        raise ValueError(
            f"sample rate {rate} too low to carry {high_hz} Hz; "
            "record with .wav16 or .sln16")
    # Trim leading/trailing silence: keep frames above -40 dBFS.
    rms = np.sqrt(np.convolve(
        samples ** 2, np.ones(160) / 160, mode="same"))
    active = np.nonzero(rms > 0.01)[0]
    if active.size < rate // 2:
        raise ValueError(f"no usable signal in {path}")
    samples = samples[active[0]:active[-1]]

    spec = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
    freqs = np.fft.rfftfreq(len(samples), 1 / rate)

    low = band_energy(spec, freqs, low_hz)
    high = band_energy(spec, freqs, high_hz)
    # Noise floor: midpoint region away from both probe tones.
    noise = band_energy(spec, freqs, (low_hz + high_hz) / 2, 500)
    eps = 1e-12
    ratio_db = 20 * np.log10((high + eps) / (low + eps))
    return Verdict(
        is_hd=ratio_db > threshold_db,
        ratio_db=float(ratio_db),
        low_db=float(20 * np.log10(low + eps)),
        high_db=float(20 * np.log10(high + eps)),
        noise_db=float(20 * np.log10(noise + eps)),
        sample_rate=rate,
    )
