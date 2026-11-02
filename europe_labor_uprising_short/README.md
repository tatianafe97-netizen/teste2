# Europe Labor Uprising — YouTube Short pipeline

This folder holds an automated pipeline that builds a **50-second vertical YouTube Short** for
**GLOBAL NEWS 1.0 – NEWS IN REAL TIME**. The topic is the October–November 2026 protest wave across Europe.

| Spec | Value |
|---|---|
| Resolution | 1080 × 1920 (9:16) |
| Frame rate | 30 fps |
| Duration | exactly 50.0 s |
| Container / codecs | MP4, H.264 (yuv420p, high profile) + AAC 48 kHz, `+faststart` |

## Quick start

```bash
pip install -r requirements.txt      # numpy, Pillow (+ optional edge-tts / gTTS)
# ffmpeg + ffprobe must be on PATH
python generate_short.py              # -> output/europe_labor_uprising_short.mp4
```

Options:

- `--tts auto|edge|gtts|none`: chooses the narration backend. `auto` tries edge-tts (neural voice), then gTTS. If neither works, the video gets a music-only soundtrack.
- `--stills-only`: renders only the preview PNGs in `output/stills/`, which takes a few seconds.
- `--preset`, `--crf`: x264 quality and speed settings.

Outputs in `output/`:

- `europe_labor_uprising_short.mp4`: the Short.
- `europe_labor_uprising_short.srt`: narration captions for upload.
- `europe_labor_uprising_short.metadata.json`: title, description and tags.
- `stills/`: key-frame previews.

## What the pipeline does

1. **Content checks** (`pipeline/content.py`): confirms the seven segments cover 0–50 s with no gaps. It warns about any fact that has no source citation.
2. **Soundtrack** (`pipeline/audio.py`): makes TTS for each segment, trims silence and time-fits each clip into its slot with `atempo`, then normalizes loudness. It mixes the voice over a synthesized 100 BPM news bed (drone, pulse and hats) that ducks under the voice.
3. **Frames** (`pipeline/visuals.py`): every frame is drawn with Pillow. Each frame has the channel header with a blinking LIVE badge, a progress bar, timed captions, a "BREAKING" ticker, red flash cuts and film grain. The main area shows one of seven segment templates.
4. **Encode** (`pipeline/render.py`): raw frames are piped into ffmpeg and muxed with the soundtrack.
5. **Verify**: ffprobe checks resolution, fps, duration, codec and that an audio stream exists. The build fails if any of these don't match the Shorts spec.

The layout leaves the YouTube Shorts overlay areas clear: the right-hand action buttons and the bottom title band.

## Storyboard

| Time | Segment | On screen |
|---|---|---|
| 0.0–4.5 | Hook | "EUROPE IS ON STRIKE", crowd silhouettes, "15+ COUNTRIES · ONE WAVE" |
| 4.5–12.5 | France | Counter to **800,000** (Oct 17), then **410,000** across **289** cities & towns (Oct 24) |
| 12.5–20.0 | Scale | Bar chart: France ×2, Rome 100,000+, Madrid 25,000; "15+ COUNTRIES" |
| 20.0–29.0 | Why now | Falling real wages · speculative rents · bombs over books |
| 29.0–36.5 | Gen Z | "GEN Z BLOCKADES" · students + workers |
| 36.5–45.5 | The question | Street anger → transnational worker power? A Europe network lights up |
| 45.5–50.0 | CTA | Channel logo + FOLLOW |

## Editorial notes: read before publishing

- Every figure on screen comes from `FACTS` in `pipeline/content.py`, which holds the figures from the editorial brief. The analysis lines are framed as analysis or questions. They make no new factual claims.
- **The `source` field of each fact is empty.** Fill in the outlet or URL for each figure before publishing. The build prints a warning until you do.
- To add facts (more countries, strike dates, union names), add an entry to `FACTS` and use it in a segment's `data`. Then extend `TICKER_ITEMS` and `YOUTUBE_METADATA`.
- The Europe network in the question segment is a schematic illustration. It is not a map of protest locations; only Paris, Rome and Madrid are labelled, matching the facts.
