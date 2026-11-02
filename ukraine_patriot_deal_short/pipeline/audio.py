"""Tense radar / newsroom pulse bed (scipy) mixed 22 dB under the narration."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

from .config import DURATION, SCENES

SR = 48000
BED_BELOW_VOICE_DB = 22.0
TARGET_LUFS = -14.0      # YouTube playback reference
CEILING_DBFS = -1.5


def _rms_db(x: np.ndarray) -> float:
    x = x[np.abs(x) > 1e-4]  # ignore digital silence between scene blocks
    if x.size == 0:
        return -120.0
    return 20 * np.log10(np.sqrt(np.mean(x.astype(np.float64) ** 2)) + 1e-12)


def _env(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return a * np.exp(-t / decay)


def synth_bed(seed: int = 7) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(DURATION * SR)
    t = np.arange(n) / SR
    bed = np.zeros(n, dtype=np.float64)

    # 1) Low tension drone: detuned A1/E2 with slow swell + filtered noise air.
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t)
    drone = (np.sin(2 * np.pi * 55.0 * t) + 0.6 * np.sin(2 * np.pi * 55.4 * t)
             + 0.35 * np.sin(2 * np.pi * 82.4 * t) + 0.15 * np.sin(2 * np.pi * 110.3 * t))
    bed += 0.30 * drone * lfo
    b, a = signal.butter(2, [180, 900], btype="band", fs=SR)
    air = signal.lfilter(b, a, rng.standard_normal(n))
    bed += 0.05 * air * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t + 1.3))

    # 2) Newsroom pulse: soft sub-kick at 120 BPM, accent on the bar.
    beat = 0.5
    kn = int(0.22 * SR)
    kt = np.arange(kn) / SR
    kick = np.sin(2 * np.pi * (48 + 60 * np.exp(-kt / 0.03)) * kt) * _env(kn, 0.002, 0.07)
    for i, bt in enumerate(np.arange(0.0, DURATION, beat)):
        i0 = int(bt * SR)
        seg = kick * (1.0 if i % 4 == 0 else 0.55)
        m = min(kn, n - i0)
        bed[i0:i0 + m] += 0.9 * seg[:m]

    # 3) Telemetry ticks on the off-beats (high-passed noise blips).
    tn = int(0.03 * SR)
    hb, ha = signal.butter(2, 5000, btype="high", fs=SR)
    tick = signal.lfilter(hb, ha, rng.standard_normal(tn)) * _env(tn, 0.001, 0.008)
    for bt in np.arange(0.25, DURATION, beat):
        i0 = int(bt * SR)
        m = min(tn, n - i0)
        bed[i0:i0 + m] += 0.12 * tick[:m]

    # 4) Radar ping every 2.5 s with two echoes.
    pn = int(1.2 * SR)
    pt = np.arange(pn) / SR
    ping = (np.sin(2 * np.pi * 1320 * pt) + 0.3 * np.sin(2 * np.pi * 2640 * pt)) * _env(pn, 0.004, 0.22)
    for bt in np.arange(0.8, DURATION - 1, 2.5):
        for delay, gain in ((0.0, 0.22), (0.19, 0.09), (0.38, 0.04)):
            i0 = int((bt + delay) * SR)
            m = min(pn, n - i0)
            if m > 0:
                bed[i0:i0 + m] += gain * ping[:m]

    # 5) Filtered-noise risers into each scene cut + a low hit on the cut.
    for sc in SCENES[1:]:
        rise_len = 0.9
        rn = int(rise_len * SR)
        i0 = int((sc.start - rise_len) * SR)
        ramp = np.linspace(0, 1, rn) ** 2
        rb, ra = signal.butter(2, [800, 6000], btype="band", fs=SR)
        riser = signal.lfilter(rb, ra, rng.standard_normal(rn)) * ramp
        bed[i0:i0 + rn] += 0.25 * riser
        hn = int(0.8 * SR)
        ht = np.arange(hn) / SR
        hit = np.sin(2 * np.pi * (40 + 40 * np.exp(-ht / 0.05)) * ht) * _env(hn, 0.002, 0.25)
        j0 = int(sc.start * SR)
        m = min(hn, n - j0)
        bed[j0:j0 + m] += 0.8 * hit[:m]

    # Gentle overall low-pass to keep it under the voice, fades in/out.
    lb, la = signal.butter(2, 7000, btype="low", fs=SR)
    bed = signal.lfilter(lb, la, bed)
    fade_in, fade_out = int(0.4 * SR), int(1.8 * SR)
    bed[:fade_in] *= np.linspace(0, 1, fade_in)
    bed[-fade_out:] *= np.linspace(1, 0, fade_out)
    return bed.astype(np.float32)


def measure_lufs(x: np.ndarray) -> float:
    """Integrated loudness via FFmpeg's loudnorm analyser."""
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
         "-af", "loudnorm=print_format=json", "-f", "null", "-"],
        input=x.astype(np.float32).tobytes(), capture_output=True, check=True)
    err = res.stderr.decode(errors="ignore")
    return float(json.loads(err[err.rindex("{"): err.rindex("}") + 1])["input_i"])


def limit(x: np.ndarray, ceiling_db: float = CEILING_DBFS) -> np.ndarray:
    """Look-ahead peak limiter (5 ms look-ahead, 80 ms release)."""
    thr = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, thr / np.maximum(np.abs(x), 1e-9))
    la = int(0.005 * SR)
    need = _running_min(need, la)  # look ahead so gain is already down at the peak
    rel = np.exp(-1.0 / (0.08 * SR))
    g = np.empty_like(need)
    cur = 1.0
    for i, v in enumerate(need):  # attack instantly, release smoothly
        cur = v if v < cur else v + (cur - v) * rel
        g[i] = cur
    return x * g


def _running_min(v: np.ndarray, w: int) -> np.ndarray:
    from scipy.ndimage import minimum_filter1d
    return minimum_filter1d(v, size=2 * w + 1, mode="nearest")


def build_mix(voice: np.ndarray, out_wav: Path, bed_wav: Path) -> dict:
    """Scale the bed so its RMS sits 22 dB under the narration, then mix."""
    n = int(DURATION * SR)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]
    bed = synth_bed()
    v_db = _rms_db(voice)
    b_db = 20 * np.log10(np.sqrt(np.mean(bed.astype(np.float64) ** 2)) + 1e-12)
    target = v_db - BED_BELOW_VOICE_DB
    bed *= 10 ** ((target - b_db) / 20)
    wavfile.write(bed_wav, SR, bed)

    mix = (voice + bed).astype(np.float64)
    # loudness-normalise to -14 LUFS, then catch narration peaks with a limiter
    # (two passes: the limiter shaves a little loudness off the first one)
    gain_db, out = 0.0, mix
    for _ in range(2):
        gain_db += TARGET_LUFS - measure_lufs(out)
        out = limit(mix * 10 ** (gain_db / 20))
    mix = out.astype(np.float32)
    wavfile.write(out_wav, SR, mix)
    final = measure_lufs(mix)
    stats = {
        "voice_rms_db": round(v_db + gain_db, 2),
        "bed_rms_db": round(target + gain_db, 2),
        "bed_below_voice_db": BED_BELOW_VOICE_DB,
        "integrated_lufs": round(final, 1),
        "true_peak_ceiling_dbfs": CEILING_DBFS,
    }
    print(f"  [audio] voice RMS {stats['voice_rms_db']} dBFS, bed RMS {stats['bed_rms_db']} dBFS "
          f"(-{BED_BELOW_VOICE_DB:.0f} dB under narration); mix {final:.1f} LUFS")
    return stats
