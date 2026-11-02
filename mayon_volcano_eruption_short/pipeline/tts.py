"""edge-tts narration: one segment per scene, placed into its scene slot.

Produces
  * voiceover.mp3 – 50 s narration track (segments pinned to scene windows)
  * voiceover.vtt – word-level WebVTT cues matching voiceover.mp3 exactly
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import ssl
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from . import config as C

SR = 48000


@dataclass
class Word:
    start: float
    end: float
    text: str


# ------------------------------------------------------------------ TLS ---
def _patch_edge_tts_ssl() -> None:
    """edge-tts pins certifi's CA store. Behind a TLS-inspecting corporate /
    sandbox proxy we additionally trust the CA bundle the environment points
    to (SSL_CERT_FILE / REQUESTS_CA_BUNDLE). Verification stays ON."""
    import certifi
    import edge_tts.communicate as comm

    ctx = ssl.create_default_context(cafile=certifi.where())
    for var in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        p = os.environ.get(var)
        if p and os.path.isfile(p):
            try:
                ctx.load_verify_locations(cafile=p)
            except ssl.SSLError:
                pass
    comm._SSL_CTX = ctx


async def _synth_one(text: str, voice: str, rate: str, mp3_path: Path):
    import edge_tts

    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3_path, "wb") as fh:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append([s, s + chunk["duration"] / 1e7, chunk["text"]])
    if not words:
        raise RuntimeError(f"edge-tts returned no word boundaries for voice {voice}")
    return words


async def _synth_all(segments, voice, rate, paths):
    return await asyncio.gather(*[
        _synth_one(t, voice, rate, p) for t, p in zip(segments, paths)])


def _decode(mp3: Path, atempo: float) -> np.ndarray:
    af = f"atempo={atempo:.5f}," if atempo > 1.0005 else ""
    cmd = ["ffmpeg", "-v", "error", "-i", str(mp3), "-af", f"{af}aresample={SR}",
           "-ac", "1", "-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _vtt_ts(t: float) -> str:
    t = max(0.0, t)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words: list[Word], path: Path) -> None:
    lines = ["WEBVTT", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{_vtt_ts(w.start)} --> {_vtt_ts(w.end)}", w.text, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def read_vtt(path: Path) -> list[Word]:
    def ts(s: str) -> float:
        parts = s.strip().split(":")
        parts = [float(p) for p in parts]
        while len(parts) < 3:
            parts.insert(0, 0.0)
        return parts[0] * 3600 + parts[1] * 60 + parts[2]

    words, block = [], []
    for line in path.read_text(encoding="utf-8").splitlines() + [""]:
        if line.strip():
            block.append(line.strip())
            continue
        if block:
            for j, l in enumerate(block):
                if "-->" in l:
                    a, b = [x.strip().split(" ")[0] for x in l.split("-->")]
                    text = " ".join(block[j + 1:]).strip()
                    if text:
                        words.append(Word(ts(a), ts(b), text))
                    break
        block = []
    return words


def _attach_punct(words, text):
    """edge-tts word boundaries drop punctuation; re-attach trailing marks from
    the script so captions can break on sentence / clause boundaries."""
    out, pos = [], 0
    for ws, we, wt in words:
        idx = text.find(wt, pos)
        if idx >= 0:
            end = idx + len(wt)
            m = re.match(r"[.,!?;:]+", text[end:])
            if m:
                wt = wt + m.group(0)
            pos = end
        out.append([ws, we, wt])
    return out


def _slots():
    return [(s + C.VOICE_LEAD, e - C.VOICE_TAIL) for s, e in C.SCENES]


def synthesize(segments, voice, rate, out_mp3: Path, out_vtt: Path, *,
               force=False, offline=False, log=print) -> list[Word]:
    """Generate narration + word-level VTT, cached by content hash."""
    slots = _slots()
    key = hashlib.sha256(json.dumps([segments, voice, rate, slots]).encode()).hexdigest()[:16]
    cache = C.BUILD_DIR / "tts_cache" / key
    cache.mkdir(parents=True, exist_ok=True)
    seg_paths = [cache / f"seg{i}.mp3" for i in range(len(segments))]
    meta = cache / "words.json"

    if offline:
        log("[tts] OFFLINE mode – silent narration with estimated word timings")
        seg_words = _estimate_words(segments)
        seg_audio = [np.zeros(int(SR * (w[-1][1] + 0.1)), np.float32) for w in seg_words]
    else:
        if force or not meta.exists() or not all(p.exists() for p in seg_paths):
            log(f"[tts] edge-tts voice={voice} rate={rate} ({len(segments)} segments)")
            _patch_edge_tts_ssl()
            try:
                seg_words = asyncio.run(_synth_all(segments, voice, rate, seg_paths))
            except Exception as exc:  # network / service failure
                raise RuntimeError(
                    f"edge-tts synthesis failed ({exc!r}). Check network access to "
                    "speech.platform.bing.com, or re-run with --offline for a silent draft."
                ) from exc
            meta.write_text(json.dumps(seg_words))
        else:
            log(f"[tts] using cached narration {cache.relative_to(C.ROOT)}")
            seg_words = json.loads(meta.read_text())
        seg_audio = None

    track = np.zeros(int(SR * C.DURATION), np.float32)
    all_words: list[Word] = []
    seg_words = [_attach_punct(w, t) for w, t in zip(seg_words, segments)]
    for i, (words, (s0, s1)) in enumerate(zip(seg_words, slots)):
        speech_end = words[-1][1]
        slot = s1 - s0
        atempo = max(1.0, speech_end / slot)
        if atempo > C.MAX_ATEMPO:
            log(f"[tts] WARNING segment {i+1} is {speech_end:.2f}s for a {slot:.2f}s slot – "
                f"capping speed-up at {C.MAX_ATEMPO}x (shorten the script)")
            atempo = C.MAX_ATEMPO
        audio = seg_audio[i] if seg_audio is not None else _decode(seg_paths[i], atempo)
        log(f"[tts] scene {i+1}: speech {speech_end:5.2f}s  slot {slot:5.2f}s  atempo {atempo:.3f}")
        a = int(s0 * SR)
        # never let a segment bleed into the next scene's slot
        limit = int((C.SCENES[i][1] - 0.05) * SR)
        audio = audio[: max(0, limit - a)]
        track[a:a + len(audio)] += audio
        for ws, we, wt in words:
            all_words.append(Word(s0 + ws / atempo, s0 + we / atempo, wt))

    peak = float(np.max(np.abs(track))) or 1.0
    if peak > 0.99:
        track *= 0.99 / peak
    wav = C.BUILD_DIR / "voiceover.wav"
    wavfile.write(wav, SR, (track * 32767).astype(np.int16))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame",
                    "-b:a", "192k", str(out_mp3)], check=True)
    write_vtt(all_words, out_vtt)
    log(f"[tts] wrote {out_mp3.name} + {out_vtt.name} ({len(all_words)} word cues)")
    return all_words


def _estimate_words(segments):
    out = []
    for text in segments:
        t, words = 0.05, []
        for tok in text.split():
            d = 0.12 + 0.055 * len(tok)
            words.append([t, t + d, tok.strip(".,;:!?")])
            t += d + (0.25 if tok[-1] in ".!?" else 0.04)
        out.append(words)
    return out
