"""Parallel frame rendering → H.264 segments → final MP4 mux."""
from __future__ import annotations

import multiprocessing as mp
import subprocess
import time
from pathlib import Path

from PIL import Image

from . import config as C

_R = None          # Renderer instance inherited by forked workers
_BG: Path | None = None


def _bg_reader(start: int, count: int):
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{start / C.FPS:.4f}", "-i", str(_BG),
           "-frames:v", str(count), "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{C.W}x{C.H}", "-"]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE)


def _render_chunk(args):
    idx, start, end, out = args
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{C.W}x{C.H}", "-r", str(C.FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-profile:v", "high", "-g", str(C.FPS * 2), "-threads", "2", str(out)],
        stdin=subprocess.PIPE)
    reader = _bg_reader(start, end - start) if _BG else None
    frame_bytes = C.W * C.H * 3
    last_bg = None
    for i in range(start, end):
        bg = None
        if reader is not None:
            buf = reader.stdout.read(frame_bytes)
            if len(buf) == frame_bytes:
                last_bg = Image.frombuffer("RGB", (C.W, C.H), buf, "raw", "RGB", 0, 1)
            bg = last_bg
        img = _R.frame(i, bg)
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    if reader is not None:
        reader.stdout.close()
        reader.wait()
    if enc.returncode != 0:
        raise RuntimeError(f"encoder failed for chunk {idx}")
    return idx


def render_video(renderer, bg_path: Path | None, audio_wav: Path, out_mp4: Path,
                 workers: int | None = None, log=print) -> Path:
    global _R, _BG
    _R, _BG = renderer, bg_path
    workers = workers or max(1, min(mp.cpu_count(), 8))
    seg_dir = C.BUILD_DIR / "segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    for old in seg_dir.glob("*.mp4"):
        old.unlink()
    n = C.N_FRAMES
    bounds = [round(n * k / workers) for k in range(workers + 1)]
    jobs = [(k, bounds[k], bounds[k + 1], seg_dir / f"seg_{k:02d}.mp4") for k in range(workers)]
    log(f"[render] {n} frames @ {C.W}x{C.H} {C.FPS}fps on {workers} workers")
    t0 = time.time()
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        for done in pool.imap_unordered(_render_chunk, jobs):
            log(f"[render]   chunk {done + 1}/{workers} done ({time.time() - t0:.1f}s)")
    lst = seg_dir / "list.txt"
    lst.write_text("".join(f"file '{j[3].resolve()}'\n" for j in jobs))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-i", str(audio_wav), "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{C.DURATION}",
                    "-movflags", "+faststart", str(out_mp4)], check=True)
    log(f"[render] muxed → {out_mp4} ({time.time() - t0:.1f}s)")
    return out_mp4
