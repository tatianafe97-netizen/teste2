#!/usr/bin/env python3
"""GLOBAL NEWS 1.0 - Mayon Volcano eruption YouTube Short generator.

    python make_short.py                 # English (en-US-ChristopherNeural)
    python make_short.py --lang pt       # Portuguese (pt-BR-AntonioNeural)
    python make_short.py --preview       # only render key still frames

Output: output/mayon_eruption_short.mp4 (1080x1920, 9:16, 30 fps, 50 s, H.264/AAC)
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time

from pipeline import config as C
from pipeline.content import CONTENT


def log(msg: str) -> None:
    print(msg, flush=True)


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames,"
                          "sample_rate,channels:format=duration,size", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def verify(path) -> bool:
    info = probe(path)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    fps = num / den
    checks = {
        "resolution 1080x1920": (v["width"], v["height"]) == (C.W, C.H),
        "frame rate 30 fps": abs(fps - C.FPS) < 0.01,
        f"duration ≈ {C.DURATION:.0f}s ({dur:.2f}s)": abs(dur - C.DURATION) < 0.25,
        "video codec h264": v["codec_name"] == "h264",
        "audio track aac": a is not None and a["codec_name"] == "aac",
    }
    size_mb = int(info["format"]["size"]) / 1e6
    log(f"\n[verify] {path}  ({size_mb:.1f} MB)")
    for k, ok in checks.items():
        log(f"   {'PASS' if ok else 'FAIL'}  {k}")
    return all(checks.values())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", choices=sorted(CONTENT), default="en", help="narration + on-screen language")
    ap.add_argument("--voice", help="override the edge-tts voice")
    ap.add_argument("--rate", default="+8%", help="edge-tts speaking rate (default +8%%)")
    ap.add_argument("--drone-db", type=float, default=-22.0, help="rumble drone level, dBFS RMS")
    ap.add_argument("--workers", type=int, default=None, help="parallel render processes")
    ap.add_argument("--force-tts", action="store_true", help="ignore the narration cache")
    ap.add_argument("--offline", action="store_true",
                    help="no network: silent narration with estimated caption timings (draft only)")
    ap.add_argument("--preview", action="store_true", help="render key still frames only")
    ap.add_argument("--out", help="output file name (inside output/)")
    ap.add_argument("--assets", help="B-roll folder (default: ./assets)")
    args = ap.parse_args(argv)

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            log(f"ERROR: {tool} not found on PATH")
            return 2

    t0 = time.time()
    lang = args.lang
    content = CONTENT[lang]
    suffix = "" if lang == "en" else f"_{lang}"
    C.BUILD_DIR.mkdir(exist_ok=True)
    C.OUTPUT_DIR.mkdir(exist_ok=True)
    out_mp4 = C.OUTPUT_DIR / (args.out or f"mayon_eruption_short{suffix}.mp4")
    voice_mp3 = C.OUTPUT_DIR / f"voiceover{suffix}.mp3"
    voice_vtt = C.OUTPUT_DIR / f"voiceover{suffix}.vtt"

    # 1) narration + word-level subtitles ---------------------------------
    from pipeline import tts
    tts.synthesize(content["segments"], args.voice or content["voice"], args.rate,
                   voice_mp3, voice_vtt, force=args.force_tts, offline=args.offline, log=log)
    words = tts.read_vtt(voice_vtt)          # captions are driven by the VTT file

    # 2) B-roll hook --------------------------------------------------------
    from pipeline import broll
    from pathlib import Path
    assets = broll.find_assets(Path(args.assets) if args.assets else C.ASSETS_DIR)
    bg_path = None
    if assets:
        log(f"[broll] found {len(assets)} asset(s): {', '.join(a.name for a in assets)}")
        bg_path = broll.build_background(assets, C.BUILD_DIR / "broll_bg.mp4", log=log)
    else:
        log("[broll] assets/ is empty – using procedural ash-charcoal background")

    # 3) graphics renderer --------------------------------------------------
    from pipeline.scenes import Renderer
    log("[gfx] building matplotlib layers (height profile, Albay map)")
    renderer = Renderer(lang, words, has_broll=bg_path is not None)

    if args.preview:
        from PIL import Image
        prev = C.BUILD_DIR / "preview"
        prev.mkdir(exist_ok=True)
        for sec in (0.5, 3.0, 8.5, 14.0, 21.5, 27.0, 35.0, 40.5, 48.0):
            i = int(sec * C.FPS)
            bg = None
            if bg_path:
                raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(sec), "-i", str(bg_path),
                                      "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                     capture_output=True).stdout
                if len(raw) == C.W * C.H * 3:
                    bg = Image.frombytes("RGB", (C.W, C.H), raw)
            renderer.frame(i, bg).save(prev / f"frame_{sec:05.1f}s.png")
        log(f"[preview] stills written to {prev}")
        return 0

    # 4) audio bed + mix ----------------------------------------------------
    from pipeline import audio
    drone = audio.synth_drone(C.BUILD_DIR / "drone.wav", level_dbfs=args.drone_db)
    mix = audio.mix(C.BUILD_DIR / "voiceover.wav", drone, C.BUILD_DIR / "final_mix.wav")
    log(f"[audio] drone bed at {args.drone_db:.0f} dBFS mixed under narration")

    # 5) render + mux -------------------------------------------------------
    from pipeline.render import render_video
    render_video(renderer, bg_path, mix, out_mp4, workers=args.workers, log=log)

    ok = verify(out_mp4)
    log(f"\nDone in {time.time() - t0:.1f}s → {out_mp4}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
