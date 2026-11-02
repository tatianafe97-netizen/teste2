"""assets/ hook: any .mp4/.mov/.jpg/.png dropped into assets/ becomes a graded,
vignetted 1080x1920 background plate that sits behind the telemetry overlays."""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import config as C

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}

# High-contrast disaster grade: crushed blacks, desaturated, warm highlights,
# cool-ish shadows, heavy broadcast vignette.
GRADE = ("eq=contrast=1.35:brightness=-0.07:saturation=0.62:gamma=0.92,"
         "colorbalance=rs=-0.04:bs=0.05:rm=0.06:bm=-0.06:rh=0.12:gh=0.03:bh=-0.10,"
         "vignette=angle=PI/3.2:mode=forward,"
         "vignette=angle=PI/4.5")


def find_assets(folder: Path = C.ASSETS_DIR) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.is_file() and p.suffix.lower() in VIDEO_EXT | IMAGE_EXT)


def build_background(assets: list[Path], out: Path, duration: float = C.DURATION, log=print):
    """Concatenate assets into one graded background plate of exactly *duration* s."""
    if not assets:
        return None
    seg = duration / len(assets)
    inputs, chains = [], []
    W, H = C.W, C.H
    for i, p in enumerate(assets):
        if p.suffix.lower() in VIDEO_EXT:
            inputs += ["-stream_loop", "-1", "-t", f"{seg:.3f}", "-i", str(p)]
            chains.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"fps={C.FPS},setsar=1,format=yuv420p,trim=duration={seg:.3f},setpts=PTS-STARTPTS[v{i}]")
        else:
            # slow Ken-Burns pan across a 12% oversized still
            bw, bh = int(W * 1.12) // 2 * 2, int(H * 1.12) // 2 * 2
            inputs += ["-loop", "1", "-framerate", str(C.FPS), "-t", f"{seg:.3f}", "-i", str(p)]
            chains.append(
                f"[{i}:v]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},"
                f"crop={W}:{H}:x='(in_w-out_w)*t/{seg:.3f}':y='(in_h-out_h)*(1-t/{seg:.3f})',"
                f"fps={C.FPS},setsar=1,format=yuv420p,trim=duration={seg:.3f},setpts=PTS-STARTPTS[v{i}]")
    concat = "".join(f"[v{i}]" for i in range(len(assets)))
    fc = ";".join(chains) + f";{concat}concat=n={len(assets)}:v=1:a=0,{GRADE},format=yuv420p[bg]"
    cmd = ["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", fc, "-map", "[bg]",
           "-t", f"{duration}", "-r", str(C.FPS), "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-an", str(out)]
    log(f"[broll] grading {len(assets)} asset(s) → {out.name}")
    subprocess.run(cmd, check=True)
    return out
