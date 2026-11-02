"""edge-tts narration: one segment per scene, fitted to the scene window, merged into
voiceover.mp3 plus a word-level voiceover.vtt."""
import asyncio
import os
import ssl
import subprocess

import numpy as np

SR = 48000
LEAD_IN = 0.20      # seconds of breath before each scene's narration
TAIL_GUARD = 0.30   # keep this much clear at the end of each scene window


def _patch_ssl():
    """edge-tts pins certifi; also trust a custom CA (corporate/agent proxies) if set."""
    import certifi
    import edge_tts.communicate as comm
    ctx = ssl.create_default_context(cafile=certifi.where())
    extra = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if extra and os.path.isfile(extra):
        ctx.load_verify_locations(extra)
    comm._SSL_CTX = ctx


async def _synth(text, voice, rate, mp3_path):
    import edge_tts
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary", proxy=proxy)
    words = []
    with open(mp3_path, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append({"start": s, "end": s + chunk["duration"] / 1e7, "text": chunk["text"]})
    return words


def decode(path, tempo=1.0):
    af = ["-af", f"atempo={tempo:.4f}"] if abs(tempo - 1.0) > 1e-3 else []
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, *af, "-f", "f32le", "-ac", "1",
                          "-ar", str(SR), "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _ts(t):
    h, rem = divmod(max(t, 0.0), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


def write_vtt(words, path):
    lines = ["WEBVTT", ""]
    for i, w in enumerate(words, 1):
        lines += [str(i), f"{_ts(w['start'])} --> {_ts(w['end'])}", w["text"], ""]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def build_voiceover(segments, scenes, duration, voice, rate, build_dir, out_mp3, out_vtt, retries=3):
    """Synthesize each scene block, speed-fit it into its window, and lay it on a timeline."""
    _patch_ssl()
    timeline = np.zeros(int(duration * SR), dtype=np.float32)
    all_words = []
    for i, (text, (s0, s1)) in enumerate(zip(segments, scenes)):
        seg_mp3 = os.path.join(build_dir, f"vo_scene{i + 1}.mp3")
        for attempt in range(retries):
            try:
                words = asyncio.run(_synth(text, voice, rate, seg_mp3))
                break
            except Exception as exc:  # network hiccups
                if attempt == retries - 1:
                    raise RuntimeError(f"edge-tts failed for scene {i + 1}: {exc}") from exc
        audio = decode(seg_mp3)
        dur = len(audio) / SR
        budget = (s1 - s0) - LEAD_IN - TAIL_GUARD
        tempo = max(1.0, dur / budget)
        if tempo > 1.0:
            audio = decode(seg_mp3, tempo)
        print(f"  scene {i + 1}: {dur:5.2f}s raw -> {len(audio) / SR:5.2f}s (atempo {tempo:.3f}), "
              f"{len(words)} words")
        start = s0 + LEAD_IN
        a = int(start * SR)
        n = min(len(audio), len(timeline) - a)
        timeline[a:a + n] += audio[:n]
        for w in words:
            all_words.append({"start": start + w["start"] / tempo, "end": start + w["end"] / tempo,
                              "text": w["text"], "scene": i})

    # Loudness: normalise speech to about -16 dBFS RMS (voiced samples only).
    voiced = timeline[np.abs(timeline) > 1e-3]
    if voiced.size:
        rms = float(np.sqrt(np.mean(voiced ** 2)))
        timeline *= (10 ** (-16 / 20)) / max(rms, 1e-6)
    peak = float(np.max(np.abs(timeline)))
    if peak > 0.97:
        timeline *= 0.97 / peak

    wav = os.path.join(build_dir, "voiceover.wav")
    _write_wav(wav, timeline)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "libmp3lame", "-b:a", "192k",
                    out_mp3], check=True)
    write_vtt(all_words, out_vtt)
    return wav, all_words


def _write_wav(path, data):
    from scipy.io import wavfile
    wavfile.write(path, SR, (np.clip(data, -1, 1) * 32767).astype(np.int16))
