# Cyclone Arnab India: YouTube Short pipeline

**GLOBAL NEWS 1.0 - NEWS IN REAL TIME** · Weather Desk

This is an automated Python pipeline. It renders a 50-second vertical Short
(1080x1920, 9:16, 30 fps, H.264/AAC MP4) on Cyclone Arnab's landfall in Andhra Pradesh,
the evacuation of more than 100,000 people, and the NDRF/medical mobilization.

```bash
./run.sh                 # creates .venv, installs deps, renders English -> cyclone_arnab_short.mp4
./run.sh --lang pt       # Portuguese (pt-BR-AntonioNeural)      -> cyclone_arnab_short_pt.mp4
```

Requirements: Python 3.10+, `ffmpeg`/`ffprobe` on PATH, and internet access for edge-tts.

## What it does

| Step | Tooling | Output |
|---|---|---|
| Voiceover | `edge-tts`: `en-US-ChristopherNeural` (or `pt-BR-AntonioNeural`) at rate `+8%` | `voiceover.mp3` |
| Word timings | edge-tts `WordBoundary` events (punctuation re-aligned from the script) | `voiceover.vtt` (word-level WebVTT) |
| Fit to 50 s | `ffprobe` + `atempo` only if narration exceeds ~48.6 s (timings rescaled) | |
| Weather drone | `scipy`: E1/A1 low-tone cluster, 150 Hz low-passed rumble, band-passed wind gusts, slow swell. Normalized to **-22 dBFS RMS**. Falls back to ffmpeg lavfi if scipy is missing | `build/drone.wav` |
| Mix | ffmpeg: voice `loudnorm` (-15 LUFS) delayed 0.35 s, drone summed underneath, limiter | `build/mix.wav` |
| B-roll hook | any `.mp4/.mov/.jpg/.png` in `assets/` is scaled, graded (contrast/teal), vignetted and looped behind the graphics | `build/broll.mp4` |
| Graphics | `matplotlib` basemaps (coastline, states, satellite texture) + `Pillow` per-frame animation | piped RGBA frames |
| Encode | ffmpeg overlay → libx264 CRF 20, yuv420p, AAC 192k, `+faststart` | `cyclone_arnab_short.mp4` |
| Verify | `ffprobe` asserts 1080x1920, 30 fps, h264/yuv420p, AAC, 50 s | console report |

## Storyboard

- **Header (all scenes):** amber `SEVERE WEATHER ALERT` hazard stripe, blinking LIVE badge, and
  `GLOBAL NEWS 1.0 • WEATHER DESK: CYCLONE ARNAB SLAMS INDIA`.
- **Scene 1 (0–12 s) · Bay of Bengal radar track:** satellite-textured map, a Doppler sweep
  from Visakhapatnam, and a rotating spiral cloud mass moving along the (illustrative) track.
  IMD intensity markers run D → DD → CS → SCS → VSCS, with a live class readout, a landfall flash
  near Narsapur/Bhimavaram, and a "weakening inland" state.
- **Scene 2 (12–25 s) · 100,000+ evacuated:** vector map with Andhra Pradesh and Odisha
  highlighted, pulsing coastal evacuation zones, shelter icons, pins on Visakhapatnam and
  Bhimavaram, a landfall-zone marker, and a count-up evacuee counter.
- **Scene 3 (25–38 s) · Emergency mobilization:** 2x2 animated metric cards (100,000+
  evacuated | ~1,100 medical teams | 30,000+ boats secured | NDRF deployed).
- **Scene 4 (38–50 s) · Aftermath & restoration:** impact tracker (casualties, flash floods,
  paddy fields, power & telecom, storm track) and the call to action
  "Follow Global News 1.0 for Real-Time Updates".
- **Captions:** bold uppercase captions of 2–4 words in the central safe zone (y ≈ 1340),
  synced to edge-tts word timestamps. The current word is highlighted in amber.
- **Lower third:** wind/gust/landfall telemetry chips and a scrolling alert ticker, both
  above YouTube's bottom UI zone.

## CLI

```
python generate_short.py [--lang en|pt] [--rate +8%] [--assets DIR] [--output FILE]
                         [--drone-db -22] [--reuse-tts] [--preview SECONDS]
```

- `--reuse-tts` skips the network call and reuses the existing voiceover and word timings.
- `--preview 5` renders only the first 5 seconds, for quick layout checks.

## Editorial notes

Facts, the discrepancies between sources, and the source links are listed in
[`SOURCES.md`](SOURCES.md). The storm track is illustrative and the map is schematic; both
are labelled on screen. Before publishing, re-check the inland track ("toward Chhattisgarh")
and the latest casualty and evacuation figures.
