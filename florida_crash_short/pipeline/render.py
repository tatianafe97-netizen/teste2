"""Frame compositor + FFmpeg encoder.

Layer order per frame:
  background (generated backdrop, or assets/ photo with Ken Burns + vignette)
  -> scene graphics -> header/breaking strip -> ticker -> captions
"""
import json
import multiprocessing as mp
import subprocess

from PIL import Image

from . import config as C
from .graphics import Captions, Header, KenBurns, Ticker, build_phrases, ease_in_out, generated_backdrop
from .scenes import SCENE_CLASSES
from .util import log

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# --------------------------------------------------------------------------- #
# assets/ hook
# --------------------------------------------------------------------------- #
def discover_photos():
    """Map scene id -> photo path.

    - `assets/scene1_*.jpg` ... `assets/scene4_*.jpg` (or `map_*`, `telemetry_*`,
      `summary_*`, `investigation_*`) pin a photo to a scene.
    - Any other images are dealt round-robin to the scenes still without one.
    - Optional `assets/credits.txt`: lines of `filename = PHOTO: AP / Name`.
    """
    if not C.ASSETS.exists():
        return {}, {}
    files = sorted(p for p in C.ASSETS.iterdir() if p.suffix.lower() in IMAGE_EXT and not p.name.startswith("."))
    ids = [s["id"] for s in C.SCENES]
    out, loose = {}, []
    for p in files:
        stem = p.stem.lower()
        hit = None
        for i, sid in enumerate(ids):
            if stem.startswith(f"scene{i + 1}") or stem.startswith(sid):
                hit = sid
        if hit and hit not in out:
            out[hit] = p
        else:
            loose.append(p)
    free = [sid for sid in ids if sid not in out]
    for k, sid in enumerate(free):
        if loose:
            out[sid] = loose[k % len(loose)]
    credits = {}
    cf = C.ASSETS / "credits.txt"
    if cf.exists():
        for line in cf.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                credits[k.strip()] = v.strip()
    return out, credits


# --------------------------------------------------------------------------- #
# Renderer (constructed once per worker process)
# --------------------------------------------------------------------------- #
class Renderer:
    def __init__(self):
        words = json.loads(C.OUTPUT_WORDS.read_text())
        self.photos, self.credits = discover_photos()
        self.backdrop = generated_backdrop()
        self.kb = {sid: KenBurns(p, seed=i) for i, (sid, p) in enumerate(self.photos.items())}
        self.scenes = [SCENE_CLASSES[s["id"]](words, photo_mode=s["id"] in self.kb) for s in C.SCENES]
        self.header = Header()
        self.ticker = Ticker(C.TICKER_ITEMS)
        self.captions = Captions(build_phrases(words, C.SCRIPT, C.CAPTION_SUBS))

    def _scene_frame(self, i, t):
        sc = C.SCENES[i]
        local = t - sc["start"]
        sid = sc["id"]
        if sid in self.kb:
            x = min(max(local / (sc["end"] - sc["start"]), 0), 1)
            img = self.kb[sid].frame(x)
            credit = self.credits.get(self.photos[sid].name)
            if credit:
                from .graphics import draw_text, font
                draw_text(img, (C.W - C.MARGIN, C.CONTENT_TOP - 14), credit.upper(), font("semi", 18),
                          (200, 208, 224), anchor="rs", tracking=1)
        else:
            img = self.backdrop.copy()
        img.alpha_composite(self.scenes[i].draw(local))
        return img

    def frame(self, n):
        t = n / C.FPS
        idx = next(i for i, s in enumerate(C.SCENES) if t < s["end"] or i == len(C.SCENES) - 1)
        img = self._scene_frame(idx, t)
        # cross-dissolve into the next scene around each boundary
        half = C.TRANSITION / 2
        for i in range(len(C.SCENES) - 1):
            b = C.SCENES[i]["end"]
            if b - half <= t < b + half:
                k = ease_in_out((t - (b - half)) / C.TRANSITION)
                a, bimg = self._scene_frame(i, t), self._scene_frame(i + 1, t)
                img = Image.blend(a, bimg, k)
        self.header.draw(img, t)
        self.ticker.draw(img, t)
        self.captions.draw(img, t)
        return img.convert("RGB")


_R = None


def _init_worker():
    global _R
    _R = Renderer()


def _render(n):
    return _R.frame(n).tobytes()


def render_video(audio_wav, workers=None, frames=None):
    words = json.loads(C.OUTPUT_WORDS.read_text())
    from .tts import write_srt
    write_srt(build_phrases(words, C.SCRIPT, C.CAPTION_SUBS), C.OUTPUT_SRT)

    photos, _ = discover_photos()
    for sid, p in photos.items():
        log(f"  assets/: {p.name} -> scene '{sid}' (Ken Burns + vignette)")
    if not photos:
        log("  assets/: no photos found -> generated broadcast backgrounds")

    workers = workers or max(1, mp.cpu_count())
    total = frames or C.N_FRAMES
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{C.W}x{C.H}", "-r", str(C.FPS), "-i", "-",
           "-i", str(audio_wav),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.2", "-g", str(C.FPS * 2), "-r", str(C.FPS),
           "-c:a", "aac", "-b:a", "192k", "-ar", str(C.AUDIO_SR), "-ac", "2",
           "-t", f"{total / C.FPS:.3f}", "-movflags", "+faststart",
           "-metadata", f"title={C.CHANNEL} - Learjet 60 crash, Greenacres FL",
           str(C.OUTPUT_VIDEO)]
    enc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    batch = workers * 8
    import sys
    ctx = mp.get_context("fork" if sys.platform.startswith("linux") else "spawn")
    try:
        with ctx.Pool(workers, initializer=_init_worker) as pool:
            for start in range(0, total, batch):
                # bounded batches keep memory flat (each frame is ~6 MB raw)
                for buf in pool.imap(_render, range(start, min(start + batch, total)), chunksize=2):
                    enc.stdin.write(buf)
                done = min(start + batch, total)
                if done % (batch * 4) < batch or done == total:
                    log(f"  rendered {done}/{total} frames")
        enc.stdin.close()
    except BrokenPipeError:
        pass
    err = enc.stderr.read().decode(errors="replace")
    if enc.wait() != 0:
        raise RuntimeError(f"ffmpeg encode failed:\n{err[-3000:]}")
    return C.OUTPUT_VIDEO


def preview_frames(times, out_dir):
    """Render individual PNG stills (no encode) for quick visual checks."""
    out_dir.mkdir(parents=True, exist_ok=True)
    r = Renderer()
    paths = []
    for t in times:
        p = out_dir / f"frame_{t:05.2f}s.png"
        r.frame(int(round(t * C.FPS))).save(p)
        paths.append(p)
    return paths
