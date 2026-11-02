#!/usr/bin/env python3
"""One-command build of the 'Europe Labor Uprising' YouTube Short.

    python generate_short.py                 # full render -> output/europe_labor_uprising_short.mp4
    python generate_short.py --tts none      # music-only (offline)
    python generate_short.py --stills-only   # quick PNG previews of key moments

Output: 1080x1920, 9:16, 30 fps, H.264/AAC MP4, exactly 50 s.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from pipeline import content  # noqa: E402
from pipeline.audio import build_soundtrack, ffmpeg_available  # noqa: E402
from pipeline.render import encode_video, export_stills, verify  # noqa: E402

STILL_TIMES = [2.0, 8.5, 16.5, 26.0, 33.0, 42.0, 48.0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=HERE / "output" / "europe_labor_uprising_short.mp4")
    ap.add_argument("--build-dir", type=Path, default=HERE / "build")
    ap.add_argument("--tts", choices=["auto", "edge", "gtts", "none"], default="auto",
                    help="narration backend (auto tries edge-tts, then gTTS, then music-only)")
    ap.add_argument("--stills-only", action="store_true", help="only export preview PNGs")
    ap.add_argument("--preset", default="medium", help="x264 preset (ultrafast..veryslow)")
    ap.add_argument("--crf", type=int, default=18)
    args = ap.parse_args()

    if not ffmpeg_available():
        print("ERROR: ffmpeg and ffprobe must be installed and on PATH.", file=sys.stderr)
        return 2

    print("[1/5] Checking editorial content")
    content.check_timeline()
    for w in content.validate_facts():
        print(f"  [facts] WARNING: {w}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.build_dir.mkdir(parents=True, exist_ok=True)

    print("[2/5] Exporting preview stills")
    stills = export_stills(args.out.parent / "stills", STILL_TIMES)
    print(f"  wrote {len(stills)} stills to {stills[0].parent}")
    if args.stills_only:
        return 0

    print("[3/5] Building soundtrack (narration + music bed)")
    audio = build_soundtrack(args.build_dir, args.tts)

    print("[4/5] Rendering and encoding video")
    encode_video(args.out, audio, crf=args.crf, preset=args.preset)

    print("[5/5] Verifying output against Shorts spec")
    report = verify(args.out)
    print("  " + json.dumps(report))

    meta = args.out.with_suffix(".metadata.json")
    meta.write_text(json.dumps(content.YOUTUBE_METADATA, indent=2, ensure_ascii=False))
    srt = args.out.with_suffix(".srt")
    srt.write_text(make_srt(), encoding="utf-8")
    print(f"\nDone: {args.out}\n  metadata: {meta}\n  captions: {srt}")
    return 0


def make_srt() -> str:
    def ts(x: float) -> str:
        ms = int(round(x * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    return "\n".join(f"{i}\n{ts(s.start)} --> {ts(s.end)}\n{s.narration}\n"
                     for i, s in enumerate(content.SEGMENTS, 1))


if __name__ == "__main__":
    sys.exit(main())
