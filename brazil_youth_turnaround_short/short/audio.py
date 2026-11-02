"""Narration assembly, documentary pulse synthesis (scipy) and final mix."""
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
LEAD = 0.30   # seconds of air before each scene's narration
TAIL = 0.35   # minimum gap before the next scene


def decode(path, tempo=1.0):
    """Decode any audio file to mono float32 at SR, optionally time-stretched."""
    af = []
    t = tempo
    while t > 2.0:  # atempo accepts 0.5..2.0 per stage
        af.append("atempo=2.0")
        t /= 2.0
    if abs(t - 1.0) > 1e-4:
        af.append(f"atempo={t:.5f}")
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if af:
        cmd += ["-af", ",".join(af)]
    cmd += ["-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def db(x):
    return 10 ** (x / 20.0)


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def tighten_pauses(x, max_pause=0.28, thresh_db=-42.0, hop=0.01):
    """Shorten silent gaps longer than max_pause (keeps delivery punchy).
    Returns (audio, time_map) where time_map(t_original) -> t_new."""
    hop_n = int(hop * SR)
    n = len(x) // hop_n
    frames = x[: n * hop_n].reshape(n, hop_n)
    loud = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9) > thresh_db
    keep = np.ones(n, bool)
    i = 0
    max_f = int(max_pause / hop)
    while i < n:
        if not loud[i]:
            j = i
            while j < n and not loud[j]:
                j += 1
            if j - i > max_f:
                # keep half the allowed pause on each side of the gap
                keep[i + max_f // 2: j - (max_f - max_f // 2)] = False
            i = j
        else:
            i += 1
    out = frames[keep].reshape(-1)
    orig_t = np.arange(n + 1) * hop
    new_t = np.concatenate([[0], np.cumsum(keep)]) * hop
    return out.astype(np.float32), lambda t: float(np.interp(t, orig_t, new_t))


def assemble_narration(segments, scenes, duration):
    """segments: list of (mp3_path, words). Places each scene's narration at the
    start of its scene window, time-compressing only if it would overrun.
    Returns (mono float32 track, flattened word timings on the global clock)."""
    track = np.zeros(int(duration * SR), dtype=np.float32)
    all_words = []
    for (mp3, words), (s0, s1) in zip(segments, scenes):
        raw, tmap = tighten_pauses(decode(mp3))
        natural = len(raw) / SR
        room = (s1 - s0) - LEAD - TAIL
        tempo = 1.0
        if natural > room:
            tempo = natural / room
            if tempo > 1.2:
                print(f"  WARNING: scene {s0:.0f}-{s1:.0f}s narration needs x{tempo:.2f} speed-up; "
                      "consider shortening the script")
            tmp = Path(str(mp3) + ".tight.wav")
            wavfile.write(str(tmp), SR, raw)
            raw = decode(tmp, tempo)
        start = s0 + LEAD
        i0 = int(start * SR)
        i1 = min(len(track), i0 + len(raw))
        track[i0:i1] += raw[: i1 - i0]
        for w in words:
            all_words.append({
                "start": round(start + tmap(w["start"]) / tempo, 3),
                "end": round(start + tmap(w["end"]) / tempo, 3),
                "text": w["text"],
                "scene": scenes.index((s0, s1)),
            })
        print(f"  scene {s0:>4.0f}-{s1:<4.0f}s narration {natural:5.2f}s  tempo x{tempo:.3f}")
    # normalise speech to a broadcast-ish level (-16 dBFS RMS over voiced parts)
    voiced = track[np.abs(track) > 0.01]
    if len(voiced):
        track *= db(-16) / rms(voiced)
    return track, all_words


def documentary_pulse(duration, scenes, bpm=84, level_db=-20.0, seed=7):
    """Deep, rhythmic heartbeat-style pulse + sub drone, low-passed, RMS at level_db dBFS."""
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n) / SR
    out = np.zeros(n, dtype=np.float64)

    def thump(f0, f1, length, amp):
        tt = np.arange(int(length * SR)) / SR
        freq = f1 + (f0 - f1) * np.exp(-tt * 18)
        phase = 2 * np.pi * np.cumsum(freq) / SR
        env = np.exp(-tt * 9) * (1 - np.exp(-tt * 400))
        return amp * np.sin(phase) * env

    lub = thump(95, 46, 0.45, 1.0)
    dub = thump(80, 42, 0.35, 0.55)
    beat = 60.0 / bpm
    bt = 0.0
    k = 0
    while bt < duration:
        i = int(bt * SR)
        for snd, off in ((lub, 0), (dub, int(0.19 * SR))):
            j = i + off
            m = min(n, j + len(snd))
            if j < n:
                out[j:m] += snd[: m - j]
        # every 4th bar: a deeper accent hit
        if k % 16 == 0:
            acc = thump(70, 32, 1.2, 1.3)
            m = min(n, i + len(acc))
            out[i:m] += acc[: m - i]
        bt += beat
        k += 1

    # sub drone (E1 + B1) with slow tremolo and filtered rumble
    drone = (0.35 * np.sin(2 * np.pi * 41.2 * t) + 0.18 * np.sin(2 * np.pi * 61.7 * t))
    drone *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.11 * t)
    rumble = rng.standard_normal(n)
    b, a = signal.butter(2, 90 / (SR / 2), "low")
    rumble = signal.lfilter(b, a, rumble) * 0.6
    out += drone + rumble

    # dynamic arc: build through scenes 1-3, breathe at scene 4, swell at the end
    env = np.interp(t,
                    [0, 1.5, scenes[1][0], scenes[2][0], scenes[3][0] - 0.2, scenes[3][0] + 0.6,
                     duration - 3, duration - 0.6, duration],
                    [0, 0.75, 0.85, 1.0, 1.0, 0.55, 1.0, 0.9, 0])
    out *= env

    b, a = signal.butter(4, 160 / (SR / 2), "low")
    out = signal.filtfilt(b, a, out)
    b, a = signal.butter(2, 25 / (SR / 2), "high")
    out = signal.filtfilt(b, a, out)
    out *= db(level_db) / rms(out)
    return out.astype(np.float32)


def soft_limit(x, ceiling_db=-1.0):
    c = db(ceiling_db)
    return (np.tanh(x / c) * c).astype(np.float32)


def write_wav(path, x):
    wavfile.write(str(path), SR, np.clip(x, -1, 1).astype(np.float32))


def encode_mp3(wav, mp3):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-c:a", "libmp3lame",
                    "-b:a", "192k", str(mp3)], check=True)


def _ts(sec):
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    s = sec % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def write_vtt(path, words):
    lines = ["WEBVTT", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{_ts(w['start'])} --> {_ts(w['end'])}", w["text"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")
