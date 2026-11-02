# GLOBAL NEWS 1.0 — Defense Desk Short: Ukraine Patriot Deal

An automated pipeline that renders a **50-second vertical YouTube Short** (1080x1920, 9:16,
30 fps, H.264/AAC MP4) on the US State Department's approval of a **$2.1B sale of 500
Patriot PAC-3 MSE interceptors to Ukraine**. The deal is paid for entirely by allies, and
new-build deliveries are not expected until the 2030s.

```
edge-tts narration ─┬─> voiceover.mp3 + word-level voiceover.vtt
                    └─> word timings ─> animation cues + burned-in captions
scipy radar/newsroom bed ─> mixed 22 dB under the narration
matplotlib (map, timeline) + Pillow (HUD, counters, flows) + optional assets/ B-roll
                    └─> raw frames piped to FFmpeg ─> ukraine_patriot_short.mp4 ─> ffprobe checks
```

## Quick start

```bash
cd ukraine_patriot_deal_short
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt     # FFmpeg must also be on PATH
.venv/bin/python generate_short.py            # English  -> ukraine_patriot_short.mp4
.venv/bin/python generate_short.py --lang pt  # PT-BR    -> ukraine_patriot_short_pt.mp4
```

| Flag | Purpose |
|---|---|
| `--lang en\|pt` | Narration, captions and on-screen text language (`en-US-ChristopherNeural` / `pt-BR-AntonioNeural`) |
| `--rate +8%` | edge-tts speaking rate (default `+8%`) |
| `--voice NAME` | Override the edge-tts voice |
| `--assets DIR` / `--no-broll` | B-roll folder (default `assets/`), or ignore it |
| `--stills 5 18 30` | Render preview frames only (fast layout check) |
| `--output PATH`, `--crf`, `--preset` | Output path and x264 quality |

A full render takes about 2 minutes on a laptop-class CPU. TTS results are cached in
`build/tts_cache/`, so a re-run only needs the network if the script changes.

## Storyboard

| Time | Scene | Visuals | Synced to the spoken word |
|---|---|---|---|
| 0–12 s | **The $2.1B Package** | 500 counter + 500-pip interceptor grid, $2.1B value tile, Lockheed Martin tile | "500", "$2.1 billion", "Lockheed" |
| 12–25 s | **Follow the Money** | Orthographic map: Canada, Germany, Norway and Brussels (EC) arcs into Kyiv, `$0 U.S. taxpayer funds` stamp, funder chips, 100%-ally-funded bar | "zero", "Canada", "Germany", "Norway", "European" |
| 25–38 s | **The 2030s Bottleneck** | Timeline (Ukraine's immediate need vs. manufacturing lead time and 2030s deliveries), "THE GAP" bracket, Kyiv's **stockpile swap & backfill** flow | "2030s", "Kyiv", "backfill" |
| 38–50 s | **Strategic Impact** | Radar scope over Ukraine with sweep, layered air-defense tiers, summary checklist, lower third "Follow Global News 1.0 for Real-Time Updates" | "shield", "Follow" |

Each scene's narration is synthesized separately and placed at that scene's start. That
keeps voice and graphics locked together. If the narration overruns 50 s, every block is
sped up by the same pitch-preserving `atempo` factor, just enough to fit (currently about
1.8%).

**Persistent chrome:** header `GLOBAL NEWS 1.0 • DEFENSE DESK: UKRAINE AIR DEFENSE` with
a LIVE badge, a scene tag strip, a scrolling ticker, and cyan scan-wipe transitions.
**Captions:** Inter Black, white with a heavy black stroke, the active word highlighted in
amber, centred at y≈1275 (the central safe zone, clear of the Shorts UI).

## Audio

`pipeline/audio.py` synthesizes the bed with numpy/scipy: a detuned low drone, a 120 BPM
sub-pulse, telemetry ticks, radar pings with echoes, and risers plus hits into each scene
cut. The bed's RMS is set **22 dB below the narration's RMS**. The mix is then
loudness-normalized to **−14 LUFS** (YouTube's playback reference), and a look-ahead
limiter caps peaks at −1.5 dBFS. Both stages apply the same gain to voice and bed, so the
22 dB gap is preserved. The measured levels are printed and saved in
`build/<lang>/report.json`.

## Files

```
generate_short.py        CLI orchestration + ffprobe verification + contact sheet
pipeline/content.py      narration (EN/PT), animation cue words, all on-screen strings
pipeline/tts.py          edge-tts synthesis, caching, timeline placement, VTT export
pipeline/audio.py        radar/newsroom bed + mix
pipeline/geo.py          matplotlib orthographic funding map + Ukraine radar scope
pipeline/charts.py       matplotlib 2026–2030s timeline
pipeline/scenes.py       the four animated scenes (Pillow)
pipeline/captions.py     karaoke-style burned-in subtitles
pipeline/render.py       background/B-roll grading, chrome, frame loop -> FFmpeg
data/geodata.json        simplified Natural Earth borders (built by tools/build_geodata.py)
assets/                  drop B-roll here (see assets/README.md)
```

**Map data:** Natural Earth 1:10m Admin-0, *Ukraine point-of-view* edition (public
domain). This edition draws Crimea as part of Ukraine, matching internationally recognised
borders. The map is labelled "schematic". It shows who funds the deal, not how much each
funder pays: no per-country split was part of the verified facts.

**Behind a TLS-inspecting proxy:** edge-tts pins certifi's CA bundle. The pipeline also
trusts `SSL_CERT_FILE` / `REQUESTS_CA_BUNDLE` when they are set.

## Editorial note

The figures come from the editorial brief: $2.1B FMS, 500 PAC-3 MSE, funding from Canada,
Germany, Norway and European Commission credit facilities, Lockheed Martin as principal
contractor, no additional US personnel, and new-build deliveries in the 2030s. Re-check
them against the official State Department / DSCA notification before publishing. The
timeline shades the 2030s without naming a specific first-delivery year.
