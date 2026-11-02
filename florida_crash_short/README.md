# florida_crash_short

An automated pipeline that builds a 45-second vertical YouTube Short (1080×1920, 9:16, 30 fps, H.264/AAC MP4)
for **GLOBAL NEWS 1.0 — NEWS IN REAL TIME**: *Learjet 60 crash, Greenacres, Palm Beach County, FL (Nov 1, 2026).*

```bash
./run.sh                      # venv + deps + full build + QA  -> output_short.mp4
./run.sh --preview 4,22.8,31  # PNG stills in build/preview/ (seconds, no encode)
./run.sh --workers 2          # limit CPU
```

Needs Python 3.10+, FFmpeg/ffprobe on PATH, and internet access for edge-tts. ImageMagick is not used.
The build takes about 2 minutes on 4 cores.

## Outputs

| File | What it is |
|---|---|
| `output_short.mp4` | Final Short with burned-in captions and mixed audio |
| `voiceover.mp3` | Narration on its 45 s timeline (edge-tts `en-US-ChristopherNeural`, +8%) |
| `voiceover.vtt` | Sentence-level timings from edge-tts |
| `captions.srt` | The phrase-level captions that are burned in (also usable as a YouTube CC upload) |
| `build/words.json` | Word-level timings (edge-tts `WordBoundary`) |
| `build/contact_sheet.jpg` | 12-frame QA sheet |

## Timeline

| Time | Scene | Driven by |
|---|---|---|
| 0–10 s | Flight path: Austin (AUS) → crash site, Greenacres → planned North Eleuthera (ELH); zooms to Palm Beach County | Natural Earth coastlines through matplotlib; animation in Pillow |
| 10–25 s | Altitude & descent: 35,250 → 8,750 ft in 60 s, live altitude/vertical-speed readouts, conditions chips, MAYDAY banner | Graph from matplotlib. The descent starts on the narrated word "entered", and MAYDAY appears on the word "mayday". |
| 25–35 s | Incident summary: Learjet 60 · 9 fatalities on board · 0 ground injuries reported · ~600 evacuated | A tile's border flashes when its number is spoken |
| 35–45 s | FAA & NTSB investigation status, crash site card, outro lower third "Follow Global News 1.0 for Real-Time Updates" | |

Every frame also carries the header bar (logo, LIVE pill, and a pulsing "BREAKING NEWS • PALM BEACH COUNTY, FL" strip), a scrolling facts ticker, and the captions. Text stays out of the Shorts UI safe zones: the top ~90 px and the bottom ~400 px.

## How it works

```
make_short.py            orchestrator (5 steps + QA; exits non-zero if QA fails)
pipeline/config.py       FACTS, script, timings, layout, palette  <- edit here
pipeline/tts.py          edge-tts, one block per scene, word timings, voiceover.mp3/.vtt
pipeline/audio.py        procedural drone (numpy/scipy), voice chain, mix, -14 LUFS
pipeline/geo.py          Natural Earth fetch, clipped and cached to data/region.json
pipeline/graphics.py     fonts, panels, header, ticker, captions, Ken Burns
pipeline/scenes.py       the 4 scenes
pipeline/render.py       compositor, multiprocess render, raw frames piped to FFmpeg
pipeline/verify.py       ffprobe specs, full decode, loudness, contact sheet
```

* **Narration and sync.** Each scene's narration is synthesized separately and placed at the scene start, so voice and graphics can't drift apart. If a block runs past its scene, the pipeline re-synthesizes it faster, up to +20%, and logs it. With the current script every block fits at +8%. Captions are aligned to edge-tts word boundaries and grouped into short phrases. The word being spoken is underlined, and spoken numbers display as numerals ("thirty-five thousand" → "35,000").
* **Audio.** The bed is synthesized in code: a detuned D-minor pad, low-passed noise, a 100 BPM sub pulse, and off-beat ticks. No samples are used, so there are no copyright issues. Its RMS is set 22 dB under the processed voice. The mix is then normalized with two-pass linear EBU R128 to about −14 LUFS, true peak ≤ −1.5 dBTP.
* **Graphics.** Every frame is composited in Pillow. Static parts (basemap, graph axes, header) are rendered once. Frames are rendered in parallel and piped as raw RGB into FFmpeg (`libx264 -crf 18`, yuv420p, `+faststart`).
* **QA.** The final step checks resolution, fps, frame count, codecs, A/V duration, a full decode with zero errors, and loudness. If any check fails, the build fails.

## Real photos: the `assets/` hook

Drop images into `assets/` and the matching scenes replace their generated backdrop with the photo. Each photo gets a slow Ken Burns zoom, a dark vignette, and translucent panels on top. You can pin a photo to a scene by file name, and add a `credits.txt` for on-screen credits. See [`assets/README.md`](assets/README.md). Wire photos from AP or Reuters need a license.

## Editorial notes

* On-screen and spoken content comes only from `FACTS` / `SCRIPT` in `config.py`.
* The flight track is a smooth curve labelled **ROUTE ILLUSTRATIVE**. The real track wasn't published.
* The descent curve is labelled **illustrative**. It matches the reported numbers exactly (35,250 → 8,750 ft in 60 s, rate within 10,000–30,000 ft/min), but the moment-by-moment shape is modelled. The MAYDAY banner is a callout tied to the narration, not a timestamp on the curve.
* The crash marker sits at the reported intersection (Military Trail & 10th Ave N), placed approximately.

## Behind a TLS-inspecting proxy

edge-tts pins certifi's CA store. If `SSL_CERT_FILE`, `REQUESTS_CA_BUNDLE` or `EDGE_TTS_CA_BUNDLE` is set, that bundle is trusted as well, and `HTTPS_PROXY` is honoured. Synthesized blocks are cached in `build/`, keyed by text, voice and rate, so re-runs don't need the network.

Fonts: Inter and JetBrains Mono (SIL OFL 1.1), bundled in `fonts/`. Map data: Natural Earth (public domain).
