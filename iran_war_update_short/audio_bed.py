"""Tense newsroom pulse bed (scipy synthesis, or an ffmpeg lavfi fallback)."""
import subprocess

import numpy as np

SR = 48000
BED_GAIN_DB = -22.0   # bed peak sits 22 dB below full scale, well under the narration


def synth_bed(duration, bpm=96, seed=7):
    from scipy import signal
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float64)

    # 1) Low tension drone: A1 + E2 fifth with slow swell, low-passed.
    lfo = 0.6 + 0.4 * np.sin(2 * np.pi * 0.07 * t)
    drone = (np.sin(2 * np.pi * 55 * t) + 0.5 * np.sin(2 * np.pi * 82.41 * t)
             + 0.25 * np.sin(2 * np.pi * 110.3 * t)) * lfo
    b, a = signal.butter(4, 300, "low", fs=SR)
    out += 0.35 * signal.lfilter(b, a, drone)

    beat = 60.0 / bpm
    # 2) Heartbeat pulse: pitched-down sine thump on every beat, accent on the downbeat.
    kn = int(0.35 * SR)
    kt = np.arange(kn) / SR
    freq = 45 + 55 * np.exp(-kt * 30)
    thump = np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-kt * 9)
    # 3) Telemetry tick on the off-beat: high-passed noise burst.
    tn = int(0.03 * SR)
    bh, ah = signal.butter(4, 5000, "high", fs=SR)
    tick = signal.lfilter(bh, ah, rng.standard_normal(tn)) * np.exp(-np.arange(tn) / SR * 160)
    # 4) Sonar ping every 4 bars.
    pn = int(1.2 * SR)
    pt = np.arange(pn) / SR
    ping = np.sin(2 * np.pi * 1318.5 * pt) * np.exp(-pt * 4.5)

    k = 0
    pos = 0.0
    while pos < duration:
        i = int(pos * SR)
        amp = 1.0 if k % 4 == 0 else 0.6
        seg = thump[: max(0, min(kn, n - i))]
        out[i:i + len(seg)] += amp * seg
        j = int((pos + beat / 2) * SR)
        if j < n:
            seg = tick[: min(tn, n - j)]
            out[j:j + len(seg)] += 0.25 * seg
        if k % 16 == 0:
            seg = ping[: max(0, min(pn, n - i))]
            out[i:i + len(seg)] += 0.12 * seg
        pos += beat
        k += 1

    # Fades + normalise to the bed level.
    fade = int(1.0 * SR)
    env = np.ones(n)
    env[:fade] = np.linspace(0, 1, fade)
    env[-fade:] = np.linspace(1, 0, fade)
    out *= env
    out /= max(np.max(np.abs(out)), 1e-9)
    out *= 10 ** (BED_GAIN_DB / 20)
    return out.astype(np.float32)


def write_bed(path, duration, method="scipy"):
    if method == "scipy":
        try:
            from scipy.io import wavfile
            wavfile.write(path, SR, (synth_bed(duration) * 32767).astype(np.int16))
            return path
        except ImportError:
            print("  scipy unavailable -> falling back to ffmpeg lavfi bed")
    # lavfi: drone + 1.6 Hz (96 BPM) decaying thump + off-beat tick, at -22 dB.
    expr = ("0.5*sin(2*PI*55*t)+0.25*sin(2*PI*82.41*t)"
            "+0.9*sin(2*PI*(45+40*exp(-30*mod(t,0.625)))*t)*exp(-9*mod(t,0.625))")
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
        "-i", f"aevalsrc='{expr}':s={SR}:d={duration}",
        "-af", f"lowpass=f=400,afade=t=in:d=1,afade=t=out:st={duration - 1}:d=1,"
               f"alimiter=limit=0.95,volume={BED_GAIN_DB}dB",
        "-ac", "1", path], check=True)
    return path
