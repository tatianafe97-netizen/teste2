#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 — Defense Desk Short: US approves $2.1B Patriot PAC-3 MSE sale to Ukraine.

Builds a 50 s, 1080x1920, 30 fps vertical MP4:
  edge-tts narration + word-level VTT  →  scipy radar/newsroom bed (-22 dB)  →
  matplotlib / Pillow broadcast graphics (+ optional B-roll from assets/)  →  FFmpeg.

Usage:
    python generate_short.py                 # English (en-US-ChristopherNeural, +8%)
    python generate_short.py --lang pt       # Portuguese (pt-BR-AntonioNeural)
    python generate_short.py --stills 5 18 30 45   # quick preview frames only
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from pipeline.config import ROOT, ASSETS_DIR, BUILD_DIR, W, H, FPS, DURATION, SCENES
from pipeline.content import NARRATION, VOICES, DEFAULT_RATE, CUES, TEXT


def resolve_cues(words, lang: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, needles in CUES[lang].items():
        for w in words:
            tok = w.text.lower()
            if any(tok.startswith(n.lower()) for n in needles):
                out[key] = w.start
                break
    return out


def probe(path: Path) -> dict:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        check=True, capture_output=True, text=True)
    return json.loads(res.stdout)


def verify(out_mp4: Path, build: Path) -> bool:
    info = probe(out_mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    fps = num / den
    dur = float(info["format"]["duration"])
    checks = {
        "resolution 1080x1920": (v["width"], v["height"]) == (W, H),
        "aspect 9:16": v["width"] * 16 == v["height"] * 9,
        "30 fps": abs(fps - FPS) < 0.01,
        "duration ≈ 50 s": abs(dur - DURATION) < 0.25,
        "H.264 video": v["codec_name"] == "h264",
        "yuv420p": v.get("pix_fmt") == "yuv420p",
        "AAC audio": a is not None and a["codec_name"] == "aac",
    }
    print("\n=== Verification:", out_mp4.name, "===")
    print(f"  {v['width']}x{v['height']} @ {fps:.2f} fps, {dur:.2f}s, "
          f"{out_mp4.stat().st_size / 1e6:.1f} MB, video={v['codec_name']}, audio={a and a['codec_name']}")
    for name, ok in checks.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")

    # contact sheet from the *encoded* file (one frame per scene midpoint + extras)
    sheet = build / "contact_sheet.jpg"
    times = [6, 18.5, 31.5, 46]
    frames = []
    for t in times:
        p = build / f"verify_{t:05.1f}.jpg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(t), "-i", str(out_mp4),
                        "-frames:v", "1", "-q:v", "3", str(p)], check=True)
        frames.append(p)
    subprocess.run(["ffmpeg", "-y", "-v", "error"] + sum([["-i", str(p)] for p in frames], []) +
                   ["-filter_complex", "".join(f"[{i}:v]scale=360:640[s{i}];" for i in range(len(frames))) +
                    "".join(f"[s{i}]" for i in range(len(frames))) + f"hstack=inputs={len(frames)}",
                    "-q:v", "3", str(sheet)], check=True)
    print(f"  contact sheet: {sheet.relative_to(ROOT)}")
    return all(checks.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=sorted(NARRATION), default="en", help="narration language (default: en)")
    ap.add_argument("--voice", help="override edge-tts voice")
    ap.add_argument("--rate", default=DEFAULT_RATE, help=f"edge-tts speaking rate (default {DEFAULT_RATE})")
    ap.add_argument("--output", type=Path, help="output MP4 path")
    ap.add_argument("--assets", type=Path, default=ASSETS_DIR, help="B-roll folder (.mp4/.jpg)")
    ap.add_argument("--no-broll", action="store_true", help="ignore assets/ and use the procedural background")
    ap.add_argument("--stills", type=float, nargs="*", help="render preview stills at these times and exit")
    ap.add_argument("--crf", type=int, default=19, help="x264 quality (lower = better, default 19)")
    ap.add_argument("--preset", default="medium", help="x264 preset (default medium)")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH — install FFmpeg first.")

    lang = args.lang
    voice = args.voice or VOICES[lang]
    suffix = "" if lang == "en" else f"_{lang}"
    out_mp4 = args.output or ROOT / f"ukraine_patriot_short{suffix}.mp4"
    vo_mp3 = ROOT / f"voiceover{suffix}.mp3"
    vo_vtt = ROOT / f"voiceover{suffix}.vtt"
    build = BUILD_DIR / lang
    build.mkdir(parents=True, exist_ok=True)
    T = TEXT[lang]

    print(f"GLOBAL NEWS 1.0 • Defense Desk Short  [lang={lang}, voice={voice}, rate={args.rate}]")

    # 1) narration
    from pipeline.tts import build_voiceover
    print("1/4 Narration (edge-tts)…")
    voice_track, words = build_voiceover(lang, voice, args.rate, NARRATION[lang], vo_mp3, vo_vtt,
                                         BUILD_DIR / "tts_cache")
    cues = resolve_cues(words, lang)
    missing = sorted(set(CUES[lang]) - set(cues))
    if missing:
        print(f"  [cues] not spoken, using default timings: {', '.join(missing)}")

    if args.stills is not None:
        from pipeline.render import render_stills
        times = args.stills or [s.start + s.dur * f for s in SCENES for f in (0.35, 0.85)]
        paths = render_stills(T, cues, words, times, build / "stills", args.assets, not args.no_broll)
        print("Stills:", *[str(p.relative_to(ROOT)) for p in paths], sep="\n  ")
        return 0

    # 2) audio bed + mix
    from pipeline.audio import build_mix
    print("2/4 Radar / newsroom bed + mix…")
    mix_wav = build / "mix.wav"
    stats = build_mix(voice_track, mix_wav, build / "bed.wav")

    # 3) video
    from pipeline.render import render_video
    print("3/4 Rendering graphics → FFmpeg…")
    render_video(T, cues, words, mix_wav, out_mp4, args.assets, not args.no_broll, args.crf, args.preset)

    # 4) verify
    print("4/4 Verifying…")
    ok = verify(out_mp4, build)
    (build / "report.json").write_text(json.dumps({"output": str(out_mp4), "audio": stats,
                                                   "cues": cues, "ok": ok}, indent=2))
    print(f"\nDone: {out_mp4}  ({'all checks passed' if ok else 'SOME CHECKS FAILED'})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
