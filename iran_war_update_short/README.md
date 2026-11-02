# GLOBAL NEWS 1.0 — Iran War Briefing Short (Nov 2026)

Automated pipeline that renders a **50-second vertical YouTube Short** (1080×1920, 9:16, 30 fps, H.264/AAC MP4)
for the channel **GLOBAL NEWS 1.0 - NEWS IN REAL TIME**.

```bash
./run.sh                 # creates .venv, installs deps, renders output/iran_war_short.mp4
./run.sh --lang pt       # Portuguese narration (pt-BR-AntonioNeural) + PT graphics -> output/iran_war_short_pt.mp4
```

Requires Python 3.10+ and `ffmpeg`/`ffprobe` on PATH. Rendering takes about 1.5 minutes.

## Outputs (`output/`)

| File | Contents |
|---|---|
| `iran_war_short.mp4` | Final Short with burned-in captions, narration and pulse bed |
| `voiceover.mp3` | edge-tts narration (`en-US-ChristopherNeural`, rate `+8%`) on the 50 s timeline |
| `voiceover.vtt` | Word-level WebVTT cues (one cue per spoken word, from edge-tts `WordBoundary` events) |
| `script.txt` | Narration per scene window |
| `*_pt.*` | Portuguese versions (`--lang pt`) |

## Structure

| Scene | Time | Graphic |
|---|---|---|
| 1 | 0–12 s | Strait of Hormuz tactical map (matplotlib): radar sweep, shipping lane vs. red "unauthorized route", 2 tanker mine-strike blasts, Brent crude counter to **$116.72/bbl** |
| 2 | 12–25 s | Pickaxe Mountain (Kūh-e Kolang Gaz Lā) cross-section south of Natanz: depth scan to **>100 m / 300+ ft**, tunnel complex, target reticle, **$47.1B** war-cost metric, Trump quote |
| 3 | 25–38 s | Qatar-mediated "Two-Day Plan" split screen: Day 1 US measures → Day 2 Hormuz reopening, plus a Saudi regional alert (Ras Tanura / Abqaiq inset map, drone intercepts) |
| 4 | 38–50 s | Diplomacy vs. escalation card (US: Trump/Rubio, Iran: Araghchi/army) + "Follow Global News 1.0 for Real-Time Updates" lower-third |

Persistent HUD: `GLOBAL NEWS 1.0 • MIDDLE EAST DESK: IRAN WAR BRIEFING` header, blinking LIVE, war-day counter
(day 248 since Feb 28, 2026), timecode, progress bar, and a BREAKING ticker.

The narration is synthesized **per scene**, then time-fitted into that scene's window (speed-up capped by the
script length, ~1.05–1.09× at present), so the voice always lines up with its graphic. Captions are bold white-on-dark
in the central safe zone (y≈1250–1440), with the spoken word highlighted in amber from the edge-tts timestamps.

## B-roll hook (`assets/`)

Put any `.mp4` / `.mov` or `.jpg` / `.png` files in `assets/`. They are assigned to scenes in sorted order
(scene *i* uses file *i mod n*). Videos loop via moviepy; stills get a slow Ken Burns push-in. Everything is
desaturated, tinted dark slate, and vignetted behind the tactical graphics. With an empty `assets/`, a slate grid
background is used. You can also point at another folder: `--assets /path/to/broll`.

## Audio

* Narration is normalized to about −16 dBFS RMS for voiced audio.
* The newsroom pulse (`audio_bed.py`, scipy) is a 96 BPM low thump, a 55 Hz drone, an off-beat telemetry tick and a sonar
  ping every 4 bars, normalized to a **−22 dBFS peak**, so it sits well under the voice. `--bed lavfi` builds a similar bed
  with ffmpeg `aevalsrc` only.

## Other flags

* `--stills 5,18,30,45` renders preview PNGs to `build/<lang>/` and exits.
* `--reuse-audio` re-renders the visuals using the existing `voiceover.mp3`/`.vtt` (works offline).
* `--crf 18` sets the x264 quality.

## Network note

edge-tts calls Microsoft's speech endpoint. Behind a TLS-intercepting proxy, set `SSL_CERT_FILE` to the proxy CA
bundle; `tts.py` adds it to edge-tts's certifi trust store and uses `HTTPS_PROXY` when set.

## Editorial note

The facts come from the November 2026 fact sheet supplied for this video. The script attributes each one to its
source (IRGC, FM Araghchi, President Trump, Secretary Rubio, Iran's army, Houthi claims). Map coastlines, tanker
positions and the mountain cross-section are **schematic and illustrative**, and are labeled that way on screen.
Re-check the figures against current wire reports before publishing. Edit `content.py` to update the script, numbers
or on-screen text.
