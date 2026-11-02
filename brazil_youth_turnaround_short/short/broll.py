"""Optional B-roll from assets/: graded, cropped to 9:16 and concatenated."""
import subprocess
from pathlib import Path

import numpy as np

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
IMAGE_EXT = {".jpg", ".jpeg", ".png"}

# High-contrast documentary grade: crushed blacks, desaturated, warm-crimson tint.
GRADE = ("eq=contrast=1.4:brightness=-0.08:saturation=0.4:gamma=0.9,"
         "curves=r='0/0 0.5/0.55 1/1':g='0/0 0.5/0.45 1/0.95':b='0/0 0.5/0.42 1/0.9',"
         "unsharp=5:5:0.6")


def find_assets(folder):
    folder = Path(folder)
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir()
                  if p.suffix.lower() in VIDEO_EXT | IMAGE_EXT and not p.name.startswith("."))


def build_broll(assets, out_path, duration, w, h, fps):
    """Concatenate assets into one graded clip of exactly `duration` seconds."""
    slot = duration / len(assets)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    filters = []
    fill = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    for i, a in enumerate(assets):
        frames = int(round(slot * fps)) + 2
        if a.suffix.lower() in IMAGE_EXT:
            cmd += ["-loop", "1", "-framerate", str(fps), "-t", f"{slot + 0.1:.3f}", "-i", str(a)]
            # slow Ken Burns push-in
            filters.append(
                f"[{i}:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,crop={w * 2}:{h * 2},"
                f"zoompan=z='min(1.0+0.0009*on,1.25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                f":d={frames}:s={w}x{h}:fps={fps},setsar=1,{GRADE},trim=end_frame={frames - 2},"
                f"setpts=PTS-STARTPTS[v{i}]")
        else:
            cmd += ["-stream_loop", "-1", "-t", f"{slot + 0.1:.3f}", "-i", str(a)]
            filters.append(f"[{i}:v]fps={fps},{fill},{GRADE},trim=end_frame={frames - 2},"
                           f"setpts=PTS-STARTPTS[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(len(assets)))
                   + f"concat=n={len(assets)}:v=1:a=0,fps={fps},format=rgb24[out]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-an",
            "-t", f"{duration:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
            "-pix_fmt", "yuv420p", str(out_path)]
    subprocess.run(cmd, check=True)
    return out_path


class FrameReader:
    """Streams RGB frames from a video; repeats the last frame if it runs short."""

    def __init__(self, path, w, h):
        self.w, self.h = w, h
        self.proc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24",
             "-s", f"{w}x{h}", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.last = np.zeros((h, w, 3), np.uint8)

    def read(self):
        n = self.w * self.h * 3
        buf = self.proc.stdout.read(n)
        if buf and len(buf) == n:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
        return self.last

    def close(self):
        self.proc.terminate()
        self.proc.stdout.close()
        self.proc.wait()
