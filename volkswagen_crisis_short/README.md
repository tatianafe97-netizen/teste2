# Volkswagen in Crisis — automated YouTube Short

**GLOBAL NEWS 1.0 - NEWS IN REAL TIME** · Economy & Labor desk

Generates a 50-second vertical Short (1080×1920, 9:16, 30 fps, H.264/AAC MP4) analysing Volkswagen's
Q3 2026 loss and its plan to make workers absorb the cost of the crisis.

```bash
./run.sh              # English, en-US-ChristopherNeural @ +8%  -> volkswagen_crisis_short.mp4
./run.sh --lang pt    # Português, pt-BR-AntonioNeural          -> volkswagen_crisis_short_pt.mp4
```

Requires Python 3.10+ and FFmpeg on `PATH`. `run.sh` creates `.venv/` and installs `requirements.txt` on first run.

## Outputs

| File | What |
|---|---|
| `volkswagen_crisis_short.mp4` | final Short (EN) |
| `voiceover.mp3` / `voiceover.vtt` | loudness-normalised narration (-16 LUFS) + word-level WebVTT timings |
| `*_pt.*` | same, Portuguese |
| `build/` | intermediates: per-scene TTS, `words_<lang>.json`, pulse bed, mix, stills |

## Timeline

| Time | Scene | Graphics |
|---|---|---|
| 0–12 s | The €5.8B Q3 collapse | loss counter, operating result Q3 2025 vs Q3 2026, deliveries / revenue % change, ≤1% margin tile |
| 12–25 s | China EV shock & tariffs | split cards (China −38.5%, €7.8B one-offs), China volume index, impairment bars, US-tariff banner |
| 25–38 s | 660,000 workers frozen | worker counter, nominal vs real pay 2026→2030 (−10%), 0% / −10% / 100K jobs tiles |
| 38–50 s | Union showdown | Board vs Unions card, "Who pays?", CTA "Follow Global News 1.0 for real-time updates" |

Narration is synthesized **per scene** and placed at each scene's start, so the voice always lands on its
graphic. If a block runs long it is time-compressed with `atempo` (the log warns above 1.18×), and the
word timings are rescaled to match.

## Pipeline

1. **Voice**: `edge-tts` with `WordBoundary` events → `voiceover.mp3` + `voiceover.vtt`.
2. **Pulse bed**: `numpy`/`scipy` synthesis (55 Hz drone, 96 BPM heartbeat kick, clock ticks, risers and
   impacts on scene cuts), peak-normalised then set to **−22 dB** (`--bed-db`). It sits about 25 LU under the voice.
3. **Graphics**: Pillow layout + matplotlib charts (animated by quantized progress, cached), rendered on
   all CPU cores and piped as raw frames into FFmpeg.
4. **Captions**: word timings are grouped into ≤3-word chunks and burned into the central safe zone (y≈1350):
   white Inter Black type with a black stroke, the active word on a red box, and a pop-in on each chunk.
5. **B-roll**: drop any `.mp4`/`.mov`/`.jpg`/`.png` into `assets/`. The files are split evenly across the
   50 s (stills get a slow Ken Burns push), then desaturated, darkened, cool-tinted, blurred slightly and
   vignetted. The graphics layer goes over them as RGBA. With `assets/` empty, a slate gradient is used.

Palette: slate grey `#0e1115/#1c2128/#2c333c`, market-crash red `#e6242b`, steel blue `#4a7fb0`, white `#f5f7fa`.
Fonts: Inter, falling back to DejaVu. To use a different font, drop `.ttf`/`.otf` files into `fonts/`.

## Options

```
--lang {en,pt}   --voice NAME   --rate +8%   --bed-db -22   --assets DIR   --out FILE
--workers N      --reuse-tts (skip TTS, reuse build/)   --preview (2 fps draft)   --stills (PNG checks)
```

## Facts and editing

Every figure lives in `content.py` (`FACTS`). The narration and on-screen copy for each language live in `STRINGS`.

Sourcing as used on screen:
- Volkswagen Group Q3 2026 results (29 Oct 2026): €5.86B operating loss (Q3 2025: −€1.29B), €5.82B net loss,
  revenue −6.3% to €75.28B, China deliveries −38.5% to ~406K, €7.8B one-off items (€6.4B Porsche goodwill,
  €1.0B China assets, €0.3B restructuring/other), 2026 operating-margin guidance of up to 1%.
- Pay freeze at 2026 levels until 2030 for ~660,000 employees, and the ~10% loss of purchasing power: as
  reported by VW's works council and IG Metall. Volkswagen has not confirmed the plan.
- The deliveries figure (1.88M, −15.1%) and "up to 100,000 jobs" follow the editorial brief. Some outlets
  report ~1.89M / −14% for deliveries, so check against the interim report before publishing.
- The real-pay curve in scene 3 is illustrative. It shows a steady path to the −10% estimate, not a forecast.
