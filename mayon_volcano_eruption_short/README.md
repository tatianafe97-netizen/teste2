# Mayon Volcano Eruption — YouTube Short pipeline

Automated generator for a **50-second vertical YouTube Short** (1080×1920, 9:16, 30 fps, H.264/AAC MP4)
for **GLOBAL NEWS 1.0 – NEWS IN REAL TIME**, styled as a disaster-monitoring desk:
volcanic-ash charcoal, alert orange, sulfur yellow and stark white telemetry.

```bash
./run.sh                 # creates .venv, installs deps, renders output/mayon_eruption_short.mp4
./run.sh --lang pt       # Portuguese narration (pt-BR-AntonioNeural) + translated graphics
```

Or by hand:

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python make_short.py [--lang en|pt] [--preview] [--force-tts] [--drone-db -22] [--assets DIR]
```

Rendering takes about 1 minute on 4 cores. Requires `ffmpeg`/`ffprobe` on PATH and network access to the
edge-tts service (`speech.platform.bing.com`). The narration is cached in `build/tts_cache/`, so
re-renders that only change graphics don't call the TTS service again.

## Outputs (`output/`)

| file | what |
|---|---|
| `mayon_eruption_short.mp4` | final Short (EN); `_pt` suffix for `--lang pt` |
| `voiceover.mp3` | 50 s narration track, each segment pinned to its scene window |
| `voiceover.vtt` | word-level WebVTT cues (edge-tts `WordBoundary`), exactly aligned to `voiceover.mp3` |

The script verifies the MP4 at the end with `ffprobe` (resolution, 30 fps, 50 s duration, h264, aac) and
exits non-zero if any check fails.

## Storyboard

| time | scene | content |
|---|---|---|
| 0–12 s | **Eruption scale** | matplotlib height profile of Mayon's cone (2,463 m), animated particle ash column rising to **+3,000 m / 9,840 ft above the crater rim** with live counters, ballistic spatter, crater glow, eruption shake + flash, PHIVOLCS badge flipping **Level 2 → 3** |
| 12–25 s | **6 km danger zone** | shaded-relief satellite-style map of Albay (procedural DEM + Albay Gulf coastline), 6 km PDZ perimeter drawn with radar sweep, evacuation corridors animating to **Tabaco City, Camalig, Ligao City** in sync with the narration |
| 25–38 s | **Emergency response** | incident summary cards: **1,430+ → 2,000+ evacuated** (740+ families), **22,000+ masks**, **lahar & ashfall hazard**, **Level 3 maintained** with a 1–5 alert meter |
| 38–50 s | **Real-time alert** | typed telemetry status board (PDZ, aviation/flight ban, shelters, ashfall, lahar) and the call to action **"Follow Global News 1.0 for real-time updates"** |

Persistent chrome: `GLOBAL NEWS 1.0 • DISASTER DESK: MAYON VOLCANO ERUPTS` header with a blinking LIVE
pill, scene progress bars, scene chip, a BREAKING ticker crawl and a sources footer. Everything important
sits above y≈1540 so YouTube's own Shorts UI doesn't cover it.

## Audio and captions

* **Voice:** `edge-tts`, `en-US-ChristopherNeural` at `+8%` (or `pt-BR-AntonioNeural` with `--lang pt`).
  Each scene's line is synthesized separately and placed in that scene's time slot. A line that runs
  slightly long gets a gentle `atempo` speed-up (at most 1.3×), and its word timings are rescaled to match.
* **Captions:** read back from `voiceover.vtt`, grouped into 1–3 word broadcast chunks that break on
  punctuation, and burned into the central safe zone (y≈1290). The word currently being spoken turns
  sulfur yellow.
* **Rumble bed:** synthesized with `scipy`: band-limited brown-noise magma rumble, a detuned 37/55/73 Hz
  sub drone, an eruption boom on the hook and soft hits on scene cuts. It is normalized to **−22 dBFS RMS**
  (`--drone-db`) and mixed under the narration. The voice is loudness-normalized to −15 LUFS, and the
  final mix lands at about −15 LUFS integrated.

## B-roll hook (`assets/`)

Drop any `.mp4/.mov/.webm` or `.jpg/.png/.webp` into `assets/`. On the next run, the clips are
cover-cropped to 9:16, still images get a slow Ken Burns pan, and everything is concatenated to fill
50 s. The result is graded (crushed blacks, desaturated, warm highlights) with a heavy broadcast vignette,
and composited behind the telemetry overlays under a translucent ash scrim. With no assets, a procedural
charcoal background with drifting ash is used instead. Use `--assets DIR` to point at another folder.

## Layout

```
make_short.py          CLI + orchestration + ffprobe verification
run.sh                 venv bootstrap + render
pipeline/config.py     canvas, timing, layout bands, palette, font discovery
pipeline/content.py    EN/PT narration (one segment per scene) + all on-screen copy
pipeline/tts.py        edge-tts synthesis, slot fitting, VTT write/read
pipeline/audio.py      scipy rumble drone + ffmpeg loudness/mix
pipeline/graphics.py   matplotlib layers: height profile chart, Albay shaded-relief map
pipeline/scenes.py     per-frame Pillow compositor (chrome, 4 scenes, FX)
pipeline/captions.py   caption chunking + burned-in rendering
pipeline/broll.py      assets/ discovery, ffmpeg grade + vignette plate
pipeline/render.py     parallel frame rendering → x264 segments → concat + AAC mux
```

## Editorial notes

Facts as briefed for the 30 Oct 2026 eruption: moderately explosive eruption at 11:53 AM; ash plume
3,000 m (9,840 ft) above the crater rim; PHIVOLCS alert raised from Level 2 to Level 3; 6 km Permanent
Danger Zone off-limits; 1,430+ evacuated, scaling past 2,000 residents / 740+ families across Tabaco
City, Camalig and Ligao City (APSEMO); 22,000+ masks distributed; lahar and livestock-contamination
warnings. Evacuation figures were still changing in early reporting, so check the latest PHIVOLCS and
APSEMO bulletins before publishing. The map is schematic: town positions and the coastline are
approximate.

If edge-tts is unreachable, `--offline` renders a silent draft with estimated caption timing. Use it for
layout checks only.
