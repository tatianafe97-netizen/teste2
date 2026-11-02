"""Narration (TTS) + synthesized music bed + mixing, all via ffmpeg/numpy.

TTS backends are tried in order: edge-tts (neural voice) -> gTTS -> none.
Each segment's narration is time-fitted into its slot with ffmpeg `atempo`,
so the voice always lines up with the visuals regardless of backend speed.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np

from .content import SEGMENTS, TOTAL_DURATION

SR = 48_000
EDGE_VOICE = "en-GB-RyanNeural"
SLOT_PADDING = 0.35          # seconds of breathing room at the end of each slot
MAX_TEMPO, MIN_TEMPO = 1.45, 0.90


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


# ----------------------------------------------------------------- TTS ----
def _tts_edge(text: str, out: Path) -> None:
    import edge_tts  # noqa: WPS433

    async def go():
        await edge_tts.Communicate(text, EDGE_VOICE, rate="+8%").save(str(out))
    asyncio.run(asyncio.wait_for(go(), timeout=30))


def _tts_gtts(text: str, out: Path) -> None:
    from gtts import gTTS  # noqa: WPS433
    gTTS(text=text, lang="en", tld="co.uk").save(str(out))


BACKENDS = {"edge": _tts_edge, "gtts": _tts_gtts}


def synth_narration(build: Path, backend: str = "auto", log=print) -> Path | None:
    """Create one 48 kHz mono WAV with every segment's narration at its start time.

    Returns None when no TTS backend works (the video then ships music-only).
    """
    order = list(BACKENDS) if backend == "auto" else [backend]
    if backend == "none":
        return None
    tts_dir = build / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)

    chosen = None
    for name in order:
        try:
            probe = tts_dir / f"_probe_{name}.mp3"
            BACKENDS[name]("Test.", probe)
            if probe.stat().st_size > 0:
                chosen = name
                break
        except Exception as exc:  # network/cert/library missing
            log(f"  [tts] backend '{name}' unavailable: {type(exc).__name__}: {str(exc)[:90]}")
    if chosen is None:
        log("  [tts] no TTS backend available -> music-only soundtrack")
        return None
    log(f"  [tts] using backend: {chosen}")

    track = np.zeros(int(TOTAL_DURATION * SR), dtype=np.float32)
    for seg in SEGMENTS:
        raw = tts_dir / f"{seg.key}_raw.mp3"
        fitted = tts_dir / f"{seg.key}.wav"
        BACKENDS[chosen](seg.narration, raw)
        dur = probe_duration(raw)
        slot = seg.duration - SLOT_PADDING - 0.15
        tempo = float(np.clip(dur / slot, MIN_TEMPO, MAX_TEMPO)) if dur > slot else 1.0
        # trim leading/trailing silence, speed-fit, normalise loudness
        af = (f"silenceremove=start_periods=1:start_threshold=-45dB,"
              f"areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
              f"atempo={tempo:.4f},loudnorm=I=-16:TP=-1.5:LRA=7")
        _run(["ffmpeg", "-y", "-i", str(raw), "-af", af, "-ar", str(SR), "-ac", "1", str(fitted)])
        voice = read_wav(fitted)
        start = int((seg.start + 0.15) * SR)
        end_limit = int((seg.end - 0.05) * SR)
        voice = voice[: max(0, end_limit - start)]
        fade = min(len(voice), int(0.04 * SR))
        if fade:
            voice[-fade:] *= np.linspace(1, 0, fade, dtype=np.float32)
        track[start:start + len(voice)] += voice
        log(f"  [tts] {seg.key:<9} {dur:5.2f}s -> tempo {tempo:.2f} -> {len(voice)/SR:5.2f}s / slot {seg.duration:.1f}s")

    out = build / "narration.wav"
    write_wav(out, track)
    return out


# --------------------------------------------------------------- music ----
def synth_music(seed: int = 7) -> np.ndarray:
    """Tense news-bed: minor drone + pulsing low hit + ticking hi-hat, 100 BPM."""
    rng = np.random.default_rng(seed)
    n = int(TOTAL_DURATION * SR)
    t = np.arange(n) / SR
    bpm = 100
    beat = 60 / bpm

    # Drone: A minor -> F -> C -> G progression, 4 bars each
    roots = [110.0, 87.31, 130.81, 98.0]
    bar = beat * 4
    chord_idx = (t // (bar * 2)).astype(int) % len(roots)
    f0 = np.array(roots)[chord_idx]
    phase = 2 * np.pi * np.cumsum(f0) / SR
    drone = (0.5 * np.sin(phase) + 0.25 * np.sin(phase * 1.5 + 0.3)
             + 0.18 * np.sin(phase * 2.0) + 0.08 * np.sin(phase * 3.0))
    drone *= 0.55 + 0.45 * np.sin(2 * np.pi * t / (bar * 2)) ** 2

    # Kick-like pulse on every beat
    pulse = np.zeros(n, dtype=np.float64)
    klen = int(0.35 * SR)
    kt = np.arange(klen) / SR
    kick = np.sin(2 * np.pi * (55 + 90 * np.exp(-kt * 30)) * kt) * np.exp(-kt * 9)
    for k in np.arange(0, TOTAL_DURATION, beat):
        i = int(k * SR)
        seg = kick[: n - i]
        pulse[i:i + len(seg)] += seg

    # Ticking hats on 8ths (filtered noise)
    hats = np.zeros(n, dtype=np.float64)
    hlen = int(0.05 * SR)
    for k in np.arange(beat / 2, TOTAL_DURATION, beat / 2):
        i = int(k * SR)
        noise = rng.standard_normal(hlen) * np.exp(-np.arange(hlen) / (0.008 * SR))
        noise = np.diff(noise, prepend=0)          # crude high-pass
        seg = noise[: n - i]
        hats[i:i + len(seg)] += seg

    mix = 0.30 * drone + 0.55 * pulse + 0.05 * hats
    # Intro swell + outro fade
    env = np.clip(t / 1.2, 0, 1) * np.clip((TOTAL_DURATION - t) / 1.5, 0, 1)
    mix *= env
    mix /= np.max(np.abs(mix)) + 1e-9
    return mix.astype(np.float32)


def build_soundtrack(build: Path, backend: str = "auto", log=print) -> Path:
    narration_path = synth_narration(build, backend, log)
    music = synth_music()
    if narration_path is not None:
        voice = read_wav(narration_path)
        # Side-chain style ducking: music drops under the voice
        env = np.abs(voice)
        win = int(0.25 * SR)
        env = np.convolve(env, np.ones(win) / win, mode="same")
        duck = 1.0 - 0.72 * np.clip(env / (env.max() * 0.25 + 1e-9), 0, 1)
        mix = 0.95 * voice + 0.32 * music * duck
    else:
        mix = 0.6 * music
    mix = mix / max(1.0, float(np.max(np.abs(mix))) / 0.95)
    out = build / "soundtrack.wav"
    write_wav(out, mix)
    return out


# ----------------------------------------------------------- wav utils ----
def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        assert w.getsampwidth() == 2, "expected 16-bit PCM"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels()).mean(axis=1)
    return (data.astype(np.float32) / 32768.0).copy()


def write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
