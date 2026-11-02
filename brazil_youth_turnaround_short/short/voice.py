"""edge-tts narration with word-level timings."""
import asyncio
import json
import os
import ssl
import time
from pathlib import Path

import edge_tts
import edge_tts.communicate as _comm


def _patch_ssl():
    """edge-tts pins certifi's CA bundle; honour a custom CA if the environment
    sets one (e.g. behind a TLS-inspecting corporate/sandbox proxy)."""
    for var in ("EDGE_TTS_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"):
        path = os.environ.get(var)
        if path and Path(path).is_file():
            _comm._SSL_CTX = ssl.create_default_context(cafile=path)
            return


async def _synth(text, voice, rate, mp3_path):
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with open(mp3_path, "wb") as fh:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({
                    "start": chunk["offset"] / 1e7,
                    "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    "text": chunk["text"],
                })
    return words


def synthesize(text, voice, rate, mp3_path, retries=4):
    """Synthesize `text` to `mp3_path`; returns word timings (seconds)."""
    _patch_ssl()
    cache = Path(str(mp3_path) + ".json")
    key = {"text": text, "voice": voice, "rate": rate}
    if cache.exists() and Path(mp3_path).exists():
        data = json.loads(cache.read_text())
        if data.get("key") == key:
            return data["words"]
    delay = 2
    for attempt in range(retries + 1):
        try:
            words = asyncio.run(_synth(text, voice, rate, mp3_path))
            if not words:
                raise RuntimeError("edge-tts returned no word boundaries")
            cache.write_text(json.dumps({"key": key, "words": words}, ensure_ascii=False))
            return words
        except Exception as exc:  # network hiccups
            if attempt == retries:
                raise
            print(f"  edge-tts failed ({exc!r}); retrying in {delay}s")
            time.sleep(delay)
            delay *= 2
