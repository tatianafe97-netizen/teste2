# GLOBAL NEWS 1.0 — Poland Constitutional Tribunal standoff (YouTube Short)

Automated pipeline that renders a **50-second vertical Short** (1080x1920, 9:16, 30 fps, H.264/AAC MP4)
for *GLOBAL NEWS 1.0 – NEWS IN REAL TIME*, Europe Desk.

## Quick start

```bash
./run.sh              # English: en-US-ChristopherNeural, rate +8%
./run.sh --lang pt    # Portuguese: pt-BR-AntonioNeural
```

Or manually:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python make_short.py [--lang en|pt] [--bed-db -22] [--assets assets/] [--out name.mp4]
```

Requires Python 3.10+, FFmpeg/ffprobe on `PATH`, and network access for edge-tts (plus a one-time download
of the Natural Earth country outlines, cached in `cache/`; without it the map falls back to a graticule).

## Outputs (`output/`)

| File | What it is |
|---|---|
| `poland_crisis_short.mp4` | the Short (`poland_crisis_short_pt.mp4` for `--lang pt`) |
| `voiceover.mp3` | narration only, loudness-normalised to −16 LUFS (`output/pt/` for Portuguese) |
| `voiceover.vtt` | word-level WebVTT timings from edge-tts `WordBoundary` events |
| `contact_sheet.jpg` | 8 stills across the four scenes for a quick visual check |
| `verification.json` | ffprobe check: resolution, 9:16, 30 fps, duration, codecs, loudness |

## Structure

| Scene | Time | Graphic |
|---|---|---|
| 1 Mid-air U-turn radar | 0–12 s | matplotlib Natural Earth map, animated illustrative track WAW → southern Spain U-turn → WAW, radar sweep, telemetry, "most tracked flight on Flightradar24" badge |
| 2 Courtroom power struggle | 12–25 s | split cards: Judge Anna Korwin-Piotrowska (acting leadership claim) vs. suspended Bogdan Święczkowski / Bartłomiej Sochański, SUSPENDED stamp, Waldemar Żurek immunity motion |
| 3 Nawrocki vs. Tusk | 25–38 s | police-light strip, high-contrast quote cards: "Forcible takeover" vs. "Restoring the rule of law — No compromise" |
| 4 Rule-of-law implications | 38–50 s | 2015 → 2017 → 2023 → 2025 → Oct 2026 timeline, EU ring, end card "Follow Global News 1.0 for Real-Time Updates" |

Persistent package: header `GLOBAL NEWS 1.0 • EUROPE DESK: WARSAW CONSTITUTIONAL CRISIS`, Polish white/crimson
stripe, BREAKING kicker per scene, progress bar, scrolling Europe Desk ticker, source line, and bold
word-highlighted captions in the central safe zone (the bottom ~25% is left clear for the Shorts UI).

## How it works

- **`script_content.py`** – script (4 segments, one per scene) for `en` and `pt`. `{Display|spoken}` markup
  keeps correct Polish spelling in captions while giving the TTS a pronounceable respelling.
- **`voice.py`** – edge-tts per segment with `WordBoundary` events; each segment is trimmed, placed on its scene
  cue and, only if it overruns the scene, sped up with `atempo` (currently ≤1.12x). Writes `voiceover.mp3`
  and `voiceover.vtt`.
- **`audio_bed.py`** – scipy-synthesised newsroom pulse (96 BPM sub pulse, clock ticks, low drone,
  tension shimmer, risers + impacts on scene changes) peaking at **−22 dBFS** (≈23 dB under the narration);
  FFmpeg `lavfi aevalsrc` fallback.
- **`basemap.py`** – radar-style map + great-circle geometry.
- **`render.py`** – Pillow frame renderer (graphics, captions, B-roll compositing) piped into FFmpeg.
- **`make_short.py`** – orchestration, mixing, contact sheet and ffprobe verification.

## Editorial notes

- Facts follow Reuters/Euronews reporting of 30 Oct 2026. Rival positions are attributed (Nawrocki: "forcible
  takeover of a constitutional body"; Tusk: rule of law "requires decisive action") rather than asserted.
- The flight track is **illustrative** (labelled on screen): heading/distance are computed from the drawn
  track, not from real transponder data.
- B-roll in `assets/` must be footage you are licensed to use.
