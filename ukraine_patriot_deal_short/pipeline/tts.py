"""edge-tts narration: per-scene synthesis, placement on the timeline, VTT export."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np

from .config import SCENES, DURATION

SR = 48000
LEAD_IN = 0.30      # seconds after a scene cut before its narration starts
MIN_GAP = 0.20      # minimum pause between scene blocks
TAIL_PAD = 0.60     # keep the last word this far from the end of the video


@dataclass
class Word:
    start: float
    end: float
    text: str
    scene: int


def _patch_ssl() -> None:
    """edge-tts pins certifi's CA bundle; also trust SSL_CERT_FILE if set
    (needed behind TLS-inspecting corporate / sandbox proxies)."""
    import edge_tts.communicate as comm
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and Path(path).is_file():
            try:
                comm._SSL_CTX.load_verify_locations(cafile=path)
            except Exception:
                pass


async def _synth(text: str, voice: str, rate: str) -> tuple[bytes, list[dict]]:
    import edge_tts
    audio = bytearray()
    words: list[dict] = []
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    async for chunk in comm.stream():
        if chunk["type"] == "audio":
            audio.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            words.append({
                "start": chunk["offset"] / 1e7,
                "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                "text": chunk["text"],
            })
    if not audio or not words:
        raise RuntimeError("edge-tts returned no audio/word boundaries")
    return bytes(audio), words


def synth_cached(text: str, voice: str, rate: str, cache_dir: Path) -> tuple[Path, list[dict]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(f"{voice}|{rate}|{text}".encode()).hexdigest()[:16]
    mp3, meta = cache_dir / f"{key}.mp3", cache_dir / f"{key}.json"
    if mp3.exists() and meta.exists():
        return mp3, json.loads(meta.read_text())
    _patch_ssl()
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            audio, words = asyncio.run(_synth(text, voice, rate))
            mp3.write_bytes(audio)
            meta.write_text(json.dumps(words))
            return mp3, words
        except Exception as e:  # network hiccups: retry with backoff
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"edge-tts failed after retries: {last_err}")


def decode(path: Path, tempo: float = 1.0) -> np.ndarray:
    """Decode audio to mono float32 @ 48 kHz (optionally time-stretched)."""
    af = ["aresample=48000"]
    if abs(tempo - 1.0) > 1e-3:
        af.insert(0, f"atempo={tempo:.4f}")
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-af", ",".join(af),
         "-ac", "1", "-f", "f32le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def build_voiceover(lang: str, voice: str, rate: str, texts: list[str],
                    out_mp3: Path, out_vtt: Path, cache_dir: Path) -> tuple[np.ndarray, list[Word]]:
    segs = [synth_cached(t, voice, rate, cache_dir) for t in texts]

    def place(tempo: float):
        clips, words, prev_end = [], [], 0.0
        for i, (mp3, wl) in enumerate(segs):
            audio = decode(mp3, tempo)
            speech_end = wl[-1]["end"] / tempo
            start = max(SCENES[i].start + LEAD_IN, prev_end + MIN_GAP)
            clips.append((start, audio))
            words += [Word(start + w["start"] / tempo, start + w["end"] / tempo, w["text"], i) for w in wl]
            prev_end = start + speech_end
        return clips, words, prev_end

    tempo = 1.0
    clips, words, end = place(tempo)
    limit = DURATION - TAIL_PAD
    if end > limit:
        # Narration overruns the 50 s slot: speed everything up uniformly
        # (pitch-preserving atempo) just enough to fit.
        total_speech = sum(w[-1]["end"] for _, w in segs)
        tempo = min(1.25, 1.0 + (end - limit) / total_speech + 0.01)
        print(f"  [tts] narration ran {end - limit:.2f}s past the slot; applying atempo={tempo:.3f}")
        clips, words, end = place(tempo)

    track = np.zeros(int(DURATION * SR) + SR, dtype=np.float32)
    for start, audio in clips:
        i0 = int(start * SR)
        n = min(len(audio), len(track) - i0)
        track[i0:i0 + n] += audio[:n]
    track = track[: int(DURATION * SR)]

    # voiceover.mp3
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1",
         "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", str(out_mp3)],
        input=track.tobytes(), check=True,
    )
    write_vtt(words, out_vtt)
    (cache_dir.parent / f"words_{lang}.json").write_text(json.dumps(
        {"lang": lang, "voice": voice, "rate": rate, "tempo": tempo,
         "words": [asdict(w) for w in words]}, indent=1, ensure_ascii=False))
    print(f"  [tts] {len(words)} words, speech ends at {end:.2f}s")
    return track, words


def _ts(t: float) -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words: list[Word], path: Path) -> None:
    lines = ["WEBVTT", "Kind: captions", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{_ts(w.start)} --> {_ts(w.end)}", w.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
