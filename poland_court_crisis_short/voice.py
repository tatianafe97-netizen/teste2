"""Voiceover generation with edge-tts + word-level timing (.vtt / .json)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from ffmpeg_utils import ffmpeg_bin, run
from script_content import DURATION, SCENES

SR = 48000
MARKUP = re.compile(r"\{([^{}|]+)\|([^{}]+)\}")
QUOTES = str.maketrans({"“": "", "”": "", '"': "", "‘": "'", "’": "'"})


@dataclass
class Word:
    text: str      # what the captions show
    start: float   # seconds, absolute on the final timeline
    end: float
    segment: int


# --------------------------------------------------------------------- parsing
def parse_segment(src: str):
    """Return (tts_text, [(display_word, tts_char_start, tts_char_end), ...])."""
    marks: list[tuple[str, str]] = []

    def stash(m):
        marks.append((m.group(1), m.group(2)))
        return f"\x00{len(marks) - 1}\x00"

    protected = MARKUP.sub(stash, src)
    tts_parts: list[str] = []
    words: list[tuple[str, int, int]] = []
    cursor = 0
    for token in protected.split():
        disp = re.sub(r"\x00(\d+)\x00", lambda m: marks[int(m.group(1))][0], token)
        spoken = re.sub(r"\x00(\d+)\x00", lambda m: marks[int(m.group(1))][1], token)
        spoken = spoken.translate(QUOTES)
        if not re.search(r"\w", disp):  # stand-alone punctuation such as a dash
            spoken = ","
            disp = ""
        if tts_parts:
            cursor += 1  # joining space
        start = cursor
        tts_parts.append(spoken)
        cursor += len(spoken)
        if disp:
            words.append((disp, start, cursor))
    return " ".join(tts_parts), words


# ------------------------------------------------------------------------ TTS
async def _synth(text: str, voice: str, rate: str, mp3_path: Path):
    import edge_tts

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary", proxy=proxy)
    bounds = []
    with open(mp3_path, "wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                bounds.append((chunk["offset"] / 1e7, (chunk["offset"] + chunk["duration"]) / 1e7, chunk["text"]))
    return bounds


def synth(text: str, voice: str, rate: str, mp3_path: Path, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            return asyncio.run(_synth(text, voice, rate, mp3_path))
        except Exception as exc:  # network hiccups
            last = exc
            print(f"  edge-tts attempt {attempt + 1} failed: {exc}")
            import time

            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"edge-tts failed after {retries} attempts: {last}")


def align(tts_text: str, words, bounds):
    """Map display words onto TTS word-boundary times via character spans."""
    spans = []
    cur = 0
    low = tts_text.lower()
    for t0, t1, txt in bounds:
        idx = tts_text.find(txt, cur)
        if idx < 0:
            idx = low.find(txt.lower(), cur)
        if idx < 0:
            continue
        spans.append((idx, idx + len(txt), t0, t1))
        cur = idx + len(txt)
    timed = []
    for disp, a, b in words:
        hits = [(t0, t1) for (s, e, t0, t1) in spans if s < b and e > a]
        timed.append([disp, min(h[0] for h in hits) if hits else None, max(h[1] for h in hits) if hits else None])
    # interpolate any word the TTS did not report
    for i, w in enumerate(timed):
        if w[1] is None:
            prev_end = next((timed[j][2] for j in range(i - 1, -1, -1) if timed[j][2] is not None), 0.0)
            nxt = next((timed[j][1] for j in range(i + 1, len(timed)) if timed[j][1] is not None), prev_end + 0.4)
            w[1], w[2] = prev_end, max(prev_end + 0.05, nxt)
    return timed


def decode_wav(src: Path, dst: Path, tempo: float = 1.0):
    filt = f"atempo={tempo:.4f}" if abs(tempo - 1.0) > 1e-3 else "anull"
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(src), "-af", filt, "-ac", "1", "-ar", str(SR), str(dst)])
    sr, data = wavfile.read(dst)
    data = data.astype(np.float32) / (32768.0 if data.dtype == np.int16 else 1.0)
    return data


def fmt_ts(t: float) -> str:
    h, rem = divmod(max(t, 0.0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words: list[Word], path: Path):
    lines = ["WEBVTT", "Kind: captions", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{fmt_ts(w.start)} --> {fmt_ts(w.end)}", w.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------- main entry
def build_voiceover(lang_cfg: dict, build_dir: Path, out_dir: Path, lead: float = 0.3, tail: float = 0.35):
    """Synthesise every segment, fit it to its scene window and assemble.

    Returns (voice_wav_path, words) where ``voice_wav_path`` is a 50 s mono
    track already loudness-normalised and ``words`` carries absolute timings.
    """
    build_dir.mkdir(parents=True, exist_ok=True)
    track = np.zeros(int(DURATION * SR), dtype=np.float32)
    all_words: list[Word] = []
    report = []
    for i, (src, (s0, s1)) in enumerate(zip(lang_cfg["segments"], SCENES)):
        tts_text, words = parse_segment(src)
        mp3 = build_dir / f"seg{i + 1}.mp3"
        print(f"  [tts] segment {i + 1}: {len(words)} words")
        bounds = synth(tts_text, lang_cfg["voice"], lang_cfg["rate"], mp3)
        raw = decode_wav(mp3, build_dir / f"seg{i + 1}_raw.wav")
        # trim leading/trailing silence so the cue lands where we want it
        nz = np.flatnonzero(np.abs(raw) > 0.01)
        head = nz[0] / SR if len(nz) else 0.0
        speech = (nz[-1] - nz[0]) / SR if len(nz) else len(raw) / SR
        window = (s1 - s0) - lead - tail
        tempo = 1.0
        if speech > window:
            tempo = min(speech / window, 1.35)
            if speech / window > 1.35:
                print(f"  WARNING: segment {i + 1} is {speech:.1f}s for a {window:.1f}s window")
        audio = decode_wav(mp3, build_dir / f"seg{i + 1}.wav", tempo) if tempo != 1.0 else raw
        head_t = head / tempo
        start_idx = int(round(head_t * SR))
        audio = audio[start_idx:]
        place = int((s0 + lead) * SR)
        end = min(len(track), place + len(audio))
        track[place:end] += audio[: end - place]
        offset = s0 + lead - head_t
        for disp, t0, t1 in align(tts_text, words, bounds):
            all_words.append(Word(disp, offset + t0 / tempo, offset + t1 / tempo, i))
        report.append({"segment": i + 1, "speech_s": round(speech, 2), "window_s": round(window, 2), "tempo": round(tempo, 3)})
        print(f"         speech {speech:.2f}s / window {window:.2f}s -> tempo x{tempo:.3f}")

    raw_path = build_dir / "voice_raw.wav"
    wavfile.write(raw_path, SR, (np.clip(track, -1, 1) * 32767).astype(np.int16))
    norm_path = build_dir / "voice_norm.wav"
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(raw_path), "-af",
         "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,"
         "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", str(SR), "-ac", "1", str(norm_path)])
    out_dir.mkdir(parents=True, exist_ok=True)
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(norm_path), "-c:a", "libmp3lame", "-b:a", "192k",
         str(out_dir / "voiceover.mp3")])
    write_vtt(all_words, out_dir / "voiceover.vtt")
    (build_dir / "words.json").write_text(json.dumps([asdict(w) for w in all_words], ensure_ascii=False, indent=1), encoding="utf-8")
    (build_dir / "timing_report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return norm_path, all_words
