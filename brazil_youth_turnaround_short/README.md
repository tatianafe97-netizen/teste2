# GLOBAL NEWS 1.0: Brazil's Youth Uprising (YouTube Short)

An automated pipeline that renders a **50-second vertical Short** (1080×1920, 9:16, 30 fps,
H.264/AAC MP4) about the October 2026 Brazilian presidential runoff.

```bash
./setup_env.sh                       # venv + deps + fonts (needs ffmpeg on PATH)
. .venv/bin/activate
python make_short.py                 # -> brazil_youth_short.mp4    (English)
python make_short.py --lang pt       # -> brazil_youth_short_pt.mp4 (Português, pt-BR-AntonioNeural)
python make_short.py --preview 5     # first 5 s only, for quick iteration
```

Other flags: `--rate +8%`, `--voice`, `--pulse-db -20`, `--assets DIR`, `--crf`, `--maxrate`, `--out`.

## Outputs

| File | What |
|---|---|
| `brazil_youth_short.mp4` | Final Short (`_pt` suffix for Portuguese) |
| `voiceover.mp3` | Full 50 s narration track, placed on the scene clock |
| `voiceover.vtt` | Word-level WebVTT cues from edge-tts `WordBoundary` events |
| `build/<lang>/` | Intermediates (per-scene TTS, pulse.wav, mix.wav, words.json). Git ignores it. |

## How it works

1. **Narration** (`short/voice.py`, `short/audio.py`): each scene's script is synthesized
   separately with edge-tts (`en-US-ChristopherNeural`, `+8%`) and anchored to the start of
   its scene window. Sentence pauses longer than 0.28 s are trimmed to keep the delivery
   punchy. If a block would still overrun its window, it's time-compressed with `atempo`, and
   word timings are remapped to match. If the environment sets `SSL_CERT_FILE` /
   `REQUESTS_CA_BUNDLE` / `EDGE_TTS_CA_BUNDLE`, edge-tts uses that CA (useful behind TLS proxies).
2. **Documentary pulse**: scipy synthesizes a lub-dub heartbeat at 84 BPM with pitch-dropping
   kicks, an E1/B1 sub drone and filtered rumble. It's low-passed at 160 Hz, follows a
   dynamic arc across the scenes and is normalized to **-20 dBFS RMS**. Narration sits at
   about -16 dBFS RMS, and the mix is soft-limited at -1 dBFS.
3. **Graphics** (`short/visuals.py`): every frame is drawn with Pillow (bars, waffle, ring,
   timeline, manifesto cards, kinetic type). The abstention slope chart is rendered with
   matplotlib. The palette is charcoal, crimson, white and gold, with film grain, vignette,
   scanlines, flicker, and crimson-sweep + RGB-split transitions between scenes. Frames pipe
   as raw RGB straight into ffmpeg, so moviepy isn't needed.
4. **HUD**: a two-tier banner reads "GLOBAL NEWS 1.0 • SPECIAL REPORT: BRAZIL'S YOUTH UPRISING"
   with a LIVE dot, plus a progress bar and a scrolling ticker. The burned-in subtitles are
   bold upper-case, 1-3 words per chunk, and highlight the active word on the edge-tts clock.
5. **B-roll**: see `assets/README.md`.

| Time | Scene |
|---|---|
| 0–12 s | First-round deficit: animated bars 47.03% vs 45.16%, gap callout, 19.2M youth electorate (14.9M voted in R1) |
| 12–25 s | Grassroots surge: kinetic type, 80% municipality waffle, abstention 21.08% → 19.2% (matplotlib), 128.2M turnout, free transit |
| 25–38 s | Historic comeback: Oct 4 → mobilization → Oct 25 timeline, "first in history" stamp, 4th term |
| 38–50 s | Structural reality: institutional vs grassroots contrast cards, "stay mobilized beyond the ballot box" |

All figures live in `short/content.py` (`FACTS`, `NARRATION`, `TEXT`). Edit them there and both
the voice and the graphics update together.

**Fact-check note:** the election figures were supplied with the brief and haven't been
independently verified by this pipeline. Confirm them against TSE results before you publish.

Fonts: Anton and Oswald (SIL Open Font License, see `fonts/OFL-*.txt`). Falls back to DejaVu Sans Bold.
