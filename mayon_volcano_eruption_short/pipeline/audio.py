"""Low-frequency volcanic rumble drone (scipy) + final narration mix (ffmpeg)."""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from . import config as C

SR = 48000


def _lowpass(x, fc, order=4):
    sos = signal.butter(order, fc, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _bandpass(x, lo, hi, order=3):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _boom(n, t0, strength=1.0, f0=70.0, f1=28.0, decay=2.2, rng=None):
    """Deep descending thump + filtered noise burst starting at t0 seconds."""
    out = np.zeros(n, np.float64)
    a = int(t0 * SR)
    length = min(n - a, int(SR * decay * 3))
    if length <= 0:
        return out
    tt = np.arange(length) / SR
    freq = f1 + (f0 - f1) * np.exp(-tt * 2.5)
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-tt / decay) * (1 - np.exp(-tt * 60))
    noise = _lowpass(rng.standard_normal(length), 180) * np.exp(-tt / (decay * 0.6))
    out[a:a + length] = strength * (np.sin(phase) * env + 0.6 * noise / (np.std(noise) + 1e-9) * 0.35)
    return out


def synth_drone(path: Path, duration: float = C.DURATION, level_dbfs: float = -22.0,
                seed: int = 1991) -> Path:
    rng = np.random.default_rng(seed)
    n = int(SR * duration)
    t = np.arange(n) / SR

    # 1) brown-noise magma rumble, band-limited 20-140 Hz
    brown = np.cumsum(rng.standard_normal(n))
    brown -= _lowpass(brown, 2.0, order=2)            # remove DC drift
    rumble = _bandpass(brown, 20, 140)
    rumble /= np.std(rumble) + 1e-9
    rumble *= 0.75 + 0.25 * np.sin(2 * np.pi * 0.09 * t + 1.3)   # slow surge

    # 2) tonal sub drone with slow beating (detuned partials)
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.05 * t)
    tone = (np.sin(2 * np.pi * 36.7 * t) + 0.55 * np.sin(2 * np.pi * 37.15 * t)
            + 0.35 * np.sin(2 * np.pi * 55.0 * t + 0.4) + 0.18 * np.sin(2 * np.pi * 73.4 * t)) * lfo
    tone /= np.std(tone) + 1e-9

    # 3) gritty ash hiss (very quiet, band 200-900 Hz) for texture
    hiss = _bandpass(rng.standard_normal(n), 200, 900)
    hiss /= np.std(hiss) + 1e-9

    bed = 0.62 * rumble + 0.48 * tone + 0.05 * hiss

    # 4) eruption boom at the hook + soft hits on every scene change
    bed += _boom(n, 0.35, 3.2, rng=rng)
    for s, _ in C.SCENES[1:]:
        bed += _boom(n, s - 0.05, 1.1, f0=60, f1=32, decay=1.0, rng=rng)

    # fades
    fade_in, fade_out = int(0.05 * SR), int(2.0 * SR)
    bed[:fade_in] *= np.linspace(0, 1, fade_in)
    bed[-fade_out:] *= np.linspace(1, 0, fade_out) ** 1.5

    # normalise RMS to the requested level (default -22 dBFS)
    rms = np.sqrt(np.mean(bed ** 2)) + 1e-12
    bed *= (10 ** (level_dbfs / 20)) / rms
    peak = np.max(np.abs(bed))
    if peak > 0.89:                     # keep the booms from clipping
        bed = np.tanh(bed / 0.89) * 0.89

    # light stereo decorrelation
    delay = int(0.011 * SR)
    left = bed
    right = np.concatenate([np.zeros(delay), bed[:-delay]])
    stereo = np.stack([left, right], axis=1)
    wavfile.write(path, SR, (stereo * 32767).astype(np.int16))
    return path


def mix(voice_wav: Path, drone_wav: Path, out_wav: Path, duration: float = C.DURATION) -> Path:
    """Loudness-normalise the narration and lay the drone bed underneath."""
    fc = ("[0:a]aresample=48000,pan=stereo|c0=c0|c1=c0,"
          "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,"
          "loudnorm=I=-15:TP=-1.5:LRA=9,aresample=48000[v];"
          "[1:a]aresample=48000[d];"
          f"[v][d]amix=inputs=2:normalize=0:duration=longest,"
          f"alimiter=limit=0.95:level=disabled,atrim=0:{duration},apad=whole_dur={duration}[out]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(voice_wav), "-i", str(drone_wav),
                    "-filter_complex", fc, "-map", "[out]", "-ar", "48000", "-ac", "2",
                    str(out_wav)], check=True)
    return out_wav
