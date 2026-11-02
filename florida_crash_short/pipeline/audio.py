"""Procedural, copyright-free broadcast tension bed (numpy/scipy) mixed under the
voiceover so the drone's RMS sits DRONE_DB_BELOW_VOICE dB below the voice's RMS."""
import subprocess

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

from . import config as C
from .util import run, log


def _env(n, sr, fade_in=1.5, fade_out=2.5):
    e = np.ones(n)
    a, b = int(fade_in * sr), int(fade_out * sr)
    e[:a] = np.linspace(0, 1, a) ** 2
    e[-b:] = np.linspace(1, 0, b) ** 2
    return e


def synth_drone(seconds=C.DURATION, sr=C.AUDIO_SR, seed=7):
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr

    # 1) Low pad: D2 root + fifth + octave, slightly detuned pairs for width.
    pad = np.zeros(n)
    for f, amp in [(73.42, 1.0), (110.0, 0.55), (146.83, 0.35)]:
        for det in (-0.25, 0.25):
            pad += amp * np.sin(2 * np.pi * (f + det) * t + rng.uniform(0, 2 * np.pi))
    pad *= 0.65 + 0.35 * np.sin(2 * np.pi * 0.07 * t)        # slow swell

    # 2) Dark air: low-passed noise.
    air = sosfilt(butter(4, 380, "low", fs=sr, output="sos"), rng.standard_normal(n)) * 0.9

    # 3) Newsroom pulse: soft sub thump on every beat (100 BPM) + tick on off-beats.
    pulse = np.zeros(n)
    beat = 60 / 100
    thump_len = int(0.22 * sr)
    tt = np.arange(thump_len) / sr
    thump = np.sin(2 * np.pi * (58 - 18 * tt / tt[-1]) * tt) * np.exp(-tt * 18)
    tick_len = int(0.03 * sr)
    tick = sosfilt(butter(2, [2500, 6000], "band", fs=sr, output="sos"),
                   rng.standard_normal(tick_len)) * np.exp(-np.arange(tick_len) / sr * 160)
    k = 0
    while (start := int(k * beat * sr)) < n - thump_len:
        pulse[start:start + thump_len] += thump * (1.0 if k % 4 == 0 else 0.6)
        off = start + int(beat * sr / 2)
        if off + tick_len < n:
            pulse[off:off + tick_len] += tick * 0.25
        k += 1

    mix = 0.55 * pad / np.max(np.abs(pad)) + 0.25 * air / np.max(np.abs(air)) + 0.6 * pulse
    mix *= _env(n, sr)
    return mix.astype(np.float64)


def _rms_db(x, floor=1e-4):
    # RMS over non-silent samples only, so the gaps between blocks don't skew it.
    active = x[np.abs(x) > floor]
    return 20 * np.log10(np.sqrt(np.mean(active ** 2)) + 1e-12)


def build_mix():
    # Broadcast voice chain: rumble cut, gentle compression, brick-wall limiter.
    # Done before mixing so the drone level is set against the final voice.
    vproc = C.BUILD / "voice_proc.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(C.BUILD / "voice.wav"), "-af",
         "highpass=f=70,acompressor=threshold=-22dB:ratio=3:attack=4:release=90:makeup=4dB,"
         "alimiter=limit=0.89:attack=3:release=40:level=disabled",
         "-ar", str(C.AUDIO_SR), "-c:a", "pcm_s16le", str(vproc)])
    sr, voice = wavfile.read(vproc)
    voice = voice.astype(np.float64) / 32768.0
    n = int(C.DURATION * sr)
    voice = np.pad(voice, (0, max(0, n - len(voice))))[:n]

    # Bring voice to a broadcast-ish level first (peak -1.5 dBFS).
    voice *= 10 ** (-1.5 / 20) / max(np.max(np.abs(voice)), 1e-9)

    drone = synth_drone(sr=sr)[:n]
    v_db, d_db = _rms_db(voice), _rms_db(drone)
    gain = 10 ** ((v_db - C.DRONE_DB_BELOW_VOICE - d_db) / 20)
    drone *= gain
    log(f"  voice RMS {v_db:.1f} dBFS, drone RMS {_rms_db(drone):.1f} dBFS "
        f"(-{v_db - _rms_db(drone):.1f} dB under voice)")

    mix = voice + drone
    peak = np.max(np.abs(mix))
    if peak > 0.95:
        mix *= 0.95 / peak
    wavfile.write(C.BUILD / "drone.wav", sr, (drone * 32767).astype(np.int16))
    raw = C.BUILD / "mix_raw.wav"
    wavfile.write(raw, sr, (mix * 32767).astype(np.int16))
    return loudnorm(raw, C.BUILD / "mix.wav")


def loudnorm(src, dst, target=-14.0, tp=-1.5, lra=11.0):
    """Two-pass EBU R128 normalization to the YouTube reference (-14 LUFS).
    linear=true applies one static gain, so the voice/drone balance is kept."""
    import json
    import re
    flt = f"loudnorm=I={target}:TP={tp}:LRA={lra}"
    res = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src), "-af", flt + ":print_format=json",
               "-f", "null", "-"])
    m = json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", res.stderr).group(0))
    flt2 = (f"{flt}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
            f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-af", flt2, "-ar", str(C.AUDIO_SR),
         "-c:a", "pcm_s16le", str(dst)])
    log(f"  loudness {float(m['input_i']):.1f} -> {target} LUFS (linear gain, TP <= {tp} dBTP)")
    return dst
