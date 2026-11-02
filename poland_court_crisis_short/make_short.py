#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 - Poland Constitutional Tribunal standoff (YouTube Short).

Usage:
    python make_short.py              # English (en-US-ChristopherNeural, +8%)
    python make_short.py --lang pt    # Portuguese (pt-BR-AntonioNeural)

Outputs (in ./output):
    poland_crisis_short.mp4   1080x1920, 30 fps, 50 s, H.264 + AAC
    voiceover.mp3             narration only
    voiceover.vtt             word-level subtitle timings
    contact_sheet.jpg         one still per scene for a quick visual check
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from audio_bed import build_bed  # noqa: E402
from ffmpeg_utils import ffmpeg_bin, probe, run  # noqa: E402
from script_content import DURATION, FPS, HEIGHT, LANGS, WIDTH  # noqa: E402

PREVIEW_TIMES = (5.0, 9.5, 19.0, 23.0, 31.0, 36.0, 43.0, 48.5)


def mix_audio(voice_wav: Path, bed_wav: Path, out_wav: Path):
    run([ffmpeg_bin(), "-y", "-v", "error", "-i", str(voice_wav), "-i", str(bed_wav), "-filter_complex",
         "[0:a]apad,atrim=0:{d}[v];[1:a]apad,atrim=0:{d}[b];[v][b]amix=inputs=2:duration=first:normalize=0,"
         "alimiter=limit=0.95:level=disabled[out]".format(d=DURATION),
         "-map", "[out]", "-ar", "48000", "-ac", "2", str(out_wav)])
    return out_wav


def contact_sheet(build_dir: Path, out_path: Path):
    from PIL import Image

    shots = sorted(build_dir.glob("preview_*.png"))
    if not shots:
        return None
    tw, th = 270, 480
    sheet = Image.new("RGB", (tw * min(4, len(shots)), th * ((len(shots) + 3) // 4)), (0, 0, 0))
    for i, p in enumerate(shots):
        im = Image.open(p).convert("RGB").resize((tw, th))
        sheet.paste(im, ((i % 4) * tw, (i // 4) * th))
    sheet.save(out_path, quality=88)
    return out_path


def verify(mp4: Path) -> dict:
    info = probe(str(mp4))
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den
    dur = float(info["format"]["duration"])
    checks = {
        "resolution 1080x1920": (int(v["width"]), int(v["height"])) == (WIDTH, HEIGHT),
        "aspect 9:16": int(v["width"]) * 16 == int(v["height"]) * 9,
        "30 fps": abs(fps - FPS) < 0.01,
        "duration ~50s": abs(dur - DURATION) < 0.35,
        "H.264 video": v["codec_name"] == "h264",
        "AAC audio present": a is not None and a["codec_name"] == "aac",
        "yuv420p": v.get("pix_fmt") == "yuv420p",
    }
    # loudness check of the final mix
    res = run([ffmpeg_bin(), "-v", "info", "-i", str(mp4), "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    lufs = None
    for line in res.stderr.splitlines()[::-1]:
        if line.strip().startswith("I:"):
            lufs = float(line.split()[1])
            break
    report = {"file": mp4.name, "size_mb": round(mp4.stat().st_size / 1e6, 2), "width": v["width"],
              "height": v["height"], "fps": round(fps, 3), "duration_s": round(dur, 3), "video_codec": v["codec_name"],
              "audio_codec": a["codec_name"] if a else None, "integrated_loudness_lufs": lufs,
              "checks": checks, "passed": all(checks.values())}
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=sorted(LANGS), default="en", help="narration/caption language")
    ap.add_argument("--out", default=None, help="output MP4 filename")
    ap.add_argument("--bed-db", type=float, default=-22.0, help="newsroom pulse level in dB (default -22)")
    ap.add_argument("--assets", default=str(ROOT / "assets"), help="folder with optional .mp4/.jpg B-roll")
    args = ap.parse_args()

    t0 = time.time()
    lang = LANGS[args.lang]
    suffix = "" if args.lang == "en" else f"_{args.lang}"
    out_dir = ROOT / "output"
    build_dir = ROOT / "build" / args.lang
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    for old in build_dir.glob("preview_*.png"):
        old.unlink()
    out_mp4 = out_dir / (args.out or f"poland_crisis_short{suffix}.mp4")

    print(f"[1/5] Voiceover ({lang['voice']}, rate {lang['rate']})")
    from voice import build_voiceover

    voice_out = out_dir if args.lang == "en" else out_dir / args.lang
    voice_wav, words = build_voiceover(lang, build_dir, voice_out)

    print(f"[2/5] Newsroom pulse bed at {args.bed_db:.0f} dB")
    bed_wav = build_bed(build_dir / "bed.wav", args.bed_db)

    print("[3/5] Mixing narration + bed")
    mix_wav = mix_audio(voice_wav, bed_wav, build_dir / "mix.wav")

    print("[4/5] Rendering broadcast graphics + captions")
    from render import Renderer

    r = Renderer(words, args.lang, build_dir, ROOT / "cache", Path(args.assets))
    r.render(mix_wav, out_mp4, PREVIEW_TIMES)
    sheet = contact_sheet(build_dir, out_dir / f"contact_sheet{suffix}.jpg")

    print("[5/5] Verifying output")
    report = verify(out_mp4)
    (out_dir / f"verification{suffix}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, ok in report["checks"].items():
        print(f"   {'PASS' if ok else 'FAIL'}  {name}")
    print(f"   size {report['size_mb']} MB, loudness {report['integrated_loudness_lufs']} LUFS")
    print(f"Done in {time.time() - t0:.0f}s -> {out_mp4}")
    if sheet:
        print(f"Contact sheet -> {sheet}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
