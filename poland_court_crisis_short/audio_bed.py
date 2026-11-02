"""Tense broadcast newsroom pulse, synthesised with scipy (lavfi fallback)."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from ffmpeg_utils import ffmpeg_bin, run
from script_content import DURATION, SCENES

SR = 48000
BPM = 96


def _env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(1.0, t / max(attack, 1e-4)) * np.exp(-t / decay)


def synth_bed(duration: float = DURATION, seed: int = 7) -> np.ndarray:
    from scipy import signal

    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float64)
    beat = 60.0 / BPM

    # 1) low drone (D2 + A2 + D3) with slow breathing amplitude
    lfo = 0.65 + 0.35 * np.sin(2 * np.pi * 0.11 * t)
    drone = (np.sin(2 * np.pi * 73.42 * t) + 0.6 * np.sin(2 * np.pi * 110.0 * t + 0.4)
             + 0.35 * np.sin(2 * np.pi * 146.83 * t + 1.1) + 0.12 * np.sin(2 * np.pi * 155.56 * t))
    out += 0.22 * drone * lfo

    # 2) heartbeat-style sub pulse on every beat (pitch-dropping sine)
    klen = int(0.32 * SR)
    kt = np.arange(klen) / SR
    freq = 45 + 75 * np.exp(-kt * 22)
    kick = np.sin(2 * np.pi * np.cumsum(freq) / SR) * _env(klen, 0.002, 0.11)
    # 3) newsroom clock tick on 8th notes (band-passed noise)
    tlen = int(0.025 * SR)
    b, a = signal.butter(2, [2500 / (SR / 2), 6500 / (SR / 2)], btype="band")
    tick = signal.lfilter(b, a, rng.standard_normal(tlen)) * _env(tlen, 0.0005, 0.006)
    k = 0
    pos = 0.0
    while pos < duration - 0.4:
        i = int(pos * SR)
        accent = 1.0 if k % 4 == 0 else 0.7
        out[i:i + klen] += 0.9 * accent * kick[: n - i]
        j = int((pos + beat / 2) * SR)
        if j + tlen < n:
            out[j:j + tlen] += 0.35 * tick
        if k % 2 == 1:
            out[i:i + tlen] += 0.18 * tick
        pos += beat
        k += 1

    # 4) tension string: high minor-second shimmer with tremolo
    trem = 0.5 + 0.5 * np.sin(2 * np.pi * 6.0 * t)
    shimmer = (np.sin(2 * np.pi * 587.33 * t) + np.sin(2 * np.pi * 622.25 * t)) * trem
    out += 0.025 * shimmer

    # 5) riser + impact into each scene change
    b2, a2 = signal.butter(2, 1800 / (SR / 2), btype="low")
    for s0, _ in SCENES[1:]:
        rlen = int(1.4 * SR)
        noise = signal.lfilter(b2, a2, rng.standard_normal(rlen))
        ramp = np.linspace(0, 1, rlen) ** 2.2
        i0 = int(s0 * SR) - rlen
        out[i0:i0 + rlen] += 0.35 * noise * ramp
        ilen = int(1.2 * SR)
        it = np.arange(ilen) / SR
        boom = np.sin(2 * np.pi * (38 + 40 * np.exp(-it * 9)) * it) * _env(ilen, 0.003, 0.35)
        i1 = int(s0 * SR)
        out[i1:i1 + ilen] += 0.9 * boom[: n - i1]

    # gentle fades
    fin, fout = int(0.4 * SR), int(1.8 * SR)
    out[:fin] *= np.linspace(0, 1, fin)
    out[-fout:] *= np.linspace(1, 0, fout)
    out /= np.max(np.abs(out)) + 1e-9
    return out.astype(np.float32)


def build_bed(path: Path, level_db: float = -22.0) -> Path:
    """Write the bed as WAV with its peak sitting at ``level_db`` dBFS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    gain = 10 ** (level_db / 20)
    try:
        from scipy.io import wavfile

        data = synth_bed() * gain
        wavfile.write(path, SR, (data * 32767).astype(np.int16))
        print(f"  [bed] scipy newsroom pulse written at {level_db:.0f} dB")
    except Exception as exc:  # pragma: no cover - fallback path
        print(f"  [bed] scipy failed ({exc}); using ffmpeg lavfi fallback")
        beat = 60.0 / BPM
        expr = (f"0.8*sin(2*PI*(45+70*exp(-22*mod(t,{beat:.4f})))*mod(t,{beat:.4f}))*exp(-9*mod(t,{beat:.4f}))"
                f"+0.2*sin(2*PI*73.42*t)*(0.65+0.35*sin(2*PI*0.11*t))+0.12*sin(2*PI*110*t)")
        run([ffmpeg_bin(), "-y", "-v", "error", "-f", "lavfi", "-i",
             f"aevalsrc='{expr}':s={SR}:d={DURATION}", "-af",
             f"volume={level_db}dB,afade=t=out:st={DURATION - 1.8}:d=1.8", "-ac", "1", str(path)])
    return path
