"""Pipe rendered frames into ffmpeg and mux with the soundtrack; verify output."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from .content import FPS, HEIGHT, TOTAL_DURATION, WIDTH
from .visuals import Renderer


def encode_video(out_path: Path, audio_path: Path, log=print, crf: int = 18, preset: str = "medium") -> None:
    n_frames = int(round(TOTAL_DURATION * FPS))
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(audio_path),
        "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-r", str(FPS), "-g", str(FPS * 2),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{TOTAL_DURATION:.3f}", "-movflags", "+faststart",
        str(out_path),
    ]
    renderer = Renderer()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    try:
        for i in range(n_frames):
            proc.stdin.write(renderer.render(i, FPS).tobytes())
            if i % (FPS * 5) == 0:
                el = time.time() - t0
                log(f"  [video] frame {i:4d}/{n_frames}  ({el:5.1f}s elapsed)")
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    log(f"  [video] encoded {n_frames} frames in {time.time() - t0:.1f}s")


def export_stills(out_dir: Path, times: list[float]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    r = Renderer()
    paths = []
    for t in times:
        p = out_dir / f"still_{t:05.2f}s.png"
        r.render(int(t * FPS), FPS).save(p)
        paths.append(p)
    return paths


def verify(path: Path) -> dict:
    """Check the encoded file matches the YouTube Shorts spec; raise on mismatch."""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "stream=codec_type,codec_name,width,height,r_frame_rate,pix_fmt:format=duration",
         "-of", "json", str(path)], check=True, capture_output=True, text=True).stdout
    info = json.loads(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = [s for s in info["streams"] if s["codec_type"] == "audio"]
    dur = float(info["format"]["duration"])
    num, den = map(int, v["r_frame_rate"].split("/"))
    report = {"width": v["width"], "height": v["height"], "fps": num / den, "codec": v["codec_name"],
              "pix_fmt": v["pix_fmt"], "duration": round(dur, 3), "audio": a[0]["codec_name"] if a else None}
    problems = []
    if (v["width"], v["height"]) != (WIDTH, HEIGHT):
        problems.append(f"resolution {v['width']}x{v['height']}")
    if abs(num / den - FPS) > 0.01:
        problems.append(f"fps {num/den}")
    if abs(dur - TOTAL_DURATION) > 0.15:
        problems.append(f"duration {dur:.2f}s")
    if v["codec_name"] != "h264" or v["pix_fmt"] != "yuv420p":
        problems.append(f"codec {v['codec_name']}/{v['pix_fmt']}")
    if not a:
        problems.append("no audio stream")
    if problems:
        raise AssertionError("Output failed Shorts spec: " + ", ".join(problems))
    return report
