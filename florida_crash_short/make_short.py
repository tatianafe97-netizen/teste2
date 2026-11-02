#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 - automated vertical Short: Learjet 60 crash, Greenacres, FL.

Pipeline:  narration (edge-tts) -> procedural drone + mix -> map data
           -> frame render (Pillow + matplotlib) -> FFmpeg encode -> QA

Usage:
    python make_short.py                 # full build -> output_short.mp4
    python make_short.py --preview 3,13,30,41   # PNG stills only (fast)
    python make_short.py --workers 2     # limit CPU use
"""
import argparse
import shutil
import sys
import time

from pipeline import config as C
from pipeline.util import log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", help="comma-separated timestamps (s) to render as PNG stills, no encode")
    ap.add_argument("--workers", type=int, default=None, help="render processes (default: all cores)")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} not found on PATH. Install FFmpeg (e.g. `brew install ffmpeg`, `apt install ffmpeg`).")
    C.BUILD.mkdir(exist_ok=True)
    C.ASSETS.mkdir(exist_ok=True)
    t0 = time.time()

    log("[1/5] Narration (edge-tts, word-level timing)")
    from pipeline import tts
    tts.build_voiceover()
    log(f"      -> {C.OUTPUT_VOICE.name}, {C.OUTPUT_VTT.name}")

    log("[2/5] Map data (Natural Earth, public domain)")
    from pipeline import geo
    geo.load_region()

    from pipeline import render
    if args.preview:
        times = [float(x) for x in args.preview.split(",")]
        for p in render.preview_frames(times, C.BUILD / "preview"):
            log(f"      {p}")
        return

    log("[3/5] Tension bed (procedural, -22 dB under voice) + mix")
    from pipeline import audio
    mix = audio.build_mix()

    log(f"[4/5] Rendering {C.N_FRAMES} frames @ {C.W}x{C.H} {C.FPS}fps + encoding")
    render.render_video(mix, workers=args.workers)

    log("[5/5] Verifying output")
    from pipeline import verify
    problems = verify.verify()
    sheet = verify.contact_sheet()
    log(f"      contact sheet -> {sheet}")
    log(f"Done in {time.time() - t0:.0f}s -> {C.OUTPUT_VIDEO}")
    if problems:
        sys.exit("QA FAILED: " + "; ".join(problems))


if __name__ == "__main__":
    main()
