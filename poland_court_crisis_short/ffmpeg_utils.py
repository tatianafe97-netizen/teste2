"""Small helpers for locating and calling FFmpeg."""

from __future__ import annotations

import json
import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=None)
def ffmpeg_bin() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:  # optional fallback: pip install imageio-ffmpeg
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover
        raise SystemExit("FFmpeg not found. Install it (apt install ffmpeg) or `pip install imageio-ffmpeg`.") from exc


@lru_cache(maxsize=None)
def ffprobe_bin() -> str | None:
    return shutil.which("ffprobe")


def run(cmd: list[str]):
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {' '.join(cmd)}\n{res.stderr[-3000:]}")
    return res


def probe(path: str) -> dict:
    exe = ffprobe_bin()
    if not exe:
        raise RuntimeError("ffprobe not available")
    res = run([exe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", path])
    return json.loads(res.stdout)
