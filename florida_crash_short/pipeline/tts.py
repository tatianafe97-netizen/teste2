"""edge-tts narration: one synthesized block per scene, word-level timing,
assembled into a single 45 s voiceover.mp3 + voiceover.vtt.
"""
import asyncio
import hashlib
import json
import os
import ssl
import time

import certifi
import edge_tts
from edge_tts import communicate as _comm

from . import config as C
from .util import run, log

TICKS = 10_000_000  # edge-tts offsets are in 100 ns units


def _configure_network():
    """edge-tts pins certifi's CA store. Behind a TLS-inspecting proxy (corporate
    networks, sandboxes) also trust the bundle named in SSL_CERT_FILE /
    REQUESTS_CA_BUNDLE, and route through HTTPS_PROXY when set."""
    extra = os.environ.get("EDGE_TTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE") \
        or os.environ.get("REQUESTS_CA_BUNDLE")
    ctx = ssl.create_default_context(cafile=certifi.where())
    if extra and os.path.exists(extra):
        ctx.load_verify_locations(extra)
    _comm._SSL_CTX = ctx
    return os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")


async def _synth(text, voice, rate, mp3_path, proxy):
    com = edge_tts.Communicate(text, voice, rate=f"{rate:+d}%", proxy=proxy,
                               boundary="WordBoundary")
    words, sentences = [], []
    with open(mp3_path, "wb") as fh:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"text": chunk["text"],
                              "start": chunk["offset"] / TICKS,
                              "end": (chunk["offset"] + chunk["duration"]) / TICKS})
    return words


def _synth_with_retry(text, voice, rate, mp3_path, proxy, attempts=4):
    for i in range(attempts):
        try:
            words = asyncio.run(_synth(text, voice, rate, mp3_path, proxy))
            if words and os.path.getsize(mp3_path) > 1000:
                return words
            raise RuntimeError("edge-tts returned no audio/word boundaries")
        except Exception as exc:  # network hiccups, throttling
            if i == attempts - 1:
                raise
            wait = 2 ** (i + 1)
            log(f"  edge-tts failed ({exc.__class__.__name__}: {exc}); retry in {wait}s")
            time.sleep(wait)


def _sentences_from_words(text, words):
    """Group word boundaries back into sentences using the source text's
    sentence-ending punctuation."""
    import re
    norm = lambda s: len(re.sub(r"[^A-Za-z0-9]", "", s))
    sents = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    out, wi = [], 0
    for s in sents:
        # Tokenizer-agnostic alignment: consume words until their alphanumeric
        # character count covers the sentence's.
        need, got, chunk = norm(s), 0, []
        while wi < len(words) and got < need:
            chunk.append(words[wi])
            got += norm(words[wi]["text"])
            wi += 1
        if chunk:
            out.append({"text": s, "start": chunk[0]["start"], "end": chunk[-1]["end"]})
    return out


def build_voiceover():
    proxy = _configure_network()
    C.BUILD.mkdir(parents=True, exist_ok=True)
    scenes = {s["id"]: s for s in C.SCENES}
    all_words, all_sents, placements = [], [], []

    for i, block in enumerate(C.SCRIPT):
        sc = scenes[block["scene"]]
        rate, voice = C.BASE_RATE, C.VOICE
        while True:
            key = hashlib.sha1(f"{block['text']}|{voice}|{rate}".encode()).hexdigest()[:12]
            mp3 = C.BUILD / f"vo_{i}_{key}.mp3"
            meta = mp3.with_suffix(".json")
            if mp3.exists() and meta.exists():
                words = json.loads(meta.read_text())
            else:
                log(f"  synthesizing block {i + 1}/{len(C.SCRIPT)} ({voice}, {rate:+d}%)")
                try:
                    words = _synth_with_retry(block["text"], voice, rate, mp3, proxy)
                except Exception:
                    if voice == C.FALLBACK_VOICE:
                        raise
                    log(f"  {voice} unavailable, falling back to {C.FALLBACK_VOICE}")
                    voice = C.FALLBACK_VOICE
                    continue
                meta.write_text(json.dumps(words))
            # mp3 carries trailing silence; measure the spoken part
            dur = words[-1]["end"] + 0.15
            if dur <= block["max_len"] or rate >= C.MAX_RATE:
                break
            log(f"  block {i + 1} is {dur:.2f}s > {block['max_len']}s; speeding up")
            rate += 4

        if dur > block["max_len"]:
            log(f"  WARNING: block {i + 1} still {dur:.2f}s at {rate:+d}%; trim the script")
        offset = sc["start"] + block["lead_in"]
        placements.append((mp3, offset))
        log(f"  block {i + 1}: {dur:5.2f}s at {rate:+d}% -> {offset:.2f}s..{offset + dur:.2f}s"
            f" (scene ends {sc['end']:.0f}s)")
        for w in words:
            all_words.append({**w, "start": w["start"] + offset, "end": w["end"] + offset,
                              "scene": sc["id"], "block": i})
        for s in _sentences_from_words(block["text"], words):
            all_sents.append({**s, "start": s["start"] + offset, "end": s["end"] + offset})

    _assemble(placements)
    C.OUTPUT_WORDS.write_text(json.dumps(all_words, indent=1))
    _write_vtt(all_sents, C.OUTPUT_VTT)
    return all_words


def _assemble(placements):
    """Lay each block on a silent 45 s timeline -> build/voice.wav + voiceover.mp3"""
    inputs, filters = [], []
    for k, (mp3, offset) in enumerate(placements):
        inputs += ["-i", str(mp3)]
        ms = int(round(offset * 1000))
        filters.append(f"[{k}:a]aresample={C.AUDIO_SR},aformat=channel_layouts=mono,"
                       f"adelay={ms}:all=1[a{k}]")
    mix = "".join(f"[a{k}]" for k in range(len(placements)))
    filters.append(f"{mix}amix=inputs={len(placements)}:normalize=0:dropout_transition=0,"
                   f"apad,atrim=0:{C.DURATION}[out]")
    wav = C.BUILD / "voice.wav"
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[out]", "-ar", str(C.AUDIO_SR), "-ac", "1", "-c:a", "pcm_s16le", str(wav)])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "192k",
         str(C.OUTPUT_VOICE)])


def _ts(t, sep="."):
    h, rem = divmod(max(t, 0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s % 1) * 1000)) % 1000:03d}"


def _write_vtt(sents, path):
    lines = ["WEBVTT", ""]
    for i, s in enumerate(sents, 1):
        lines += [str(i), f"{_ts(s['start'])} --> {_ts(s['end'])}", s["text"], ""]
    path.write_text("\n".join(lines))


def write_srt(phrases, path):
    lines = []
    for i, p in enumerate(phrases, 1):
        lines += [str(i), f"{_ts(p['start'], ',')} --> {_ts(p['end'], ',')}", p["text"], ""]
    path.write_text("\n".join(lines))
