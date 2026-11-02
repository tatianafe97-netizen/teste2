"""Frame compositor: background / B-roll, scene graphics, chrome, captions → FFmpeg."""
from __future__ import annotations

import math
import subprocess
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .captions import CaptionRenderer
from .config import (W, H, FPS, DURATION, N_FRAMES, SCENES, MARGIN_X, HEADER_Y0, HEADER_Y1,
                     TAG_Y, TICKER_Y, NAVY_DEEP, NAVY, PANEL, CYAN, CYAN_DIM, NATO_BLUE,
                     AMBER, ALERT_RED, WHITE, GREY, rgba, font)
from .draw import text, text_size, prog, ease_out, clamp
from .scenes import SCENE_CLASSES

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


# ── backgrounds ──────────────────────────────────────────────────────────
def _vignette() -> np.ndarray:
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    nx, ny = (xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2)
    r = np.sqrt(nx ** 2 * 1.0 + ny ** 2 * 0.85)
    return np.clip(1.15 - 0.75 * r ** 1.8, 0.18, 1.0)[..., None]


def _grid_overlay() -> Image.Image:
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(g)
    for x in range(0, W, 60):
        d.line([(x, 0), (x, H)], fill=rgba(CYAN, 14), width=1)
    for y in range(0, H, 60):
        d.line([(0, y), (W, y)], fill=rgba(CYAN, 14), width=1)
    for y in range(0, H, 4):  # CRT scanlines
        d.line([(0, y), (W, y)], fill=(0, 0, 0, 28), width=1)
    return g


class Background:
    """Procedural deep-navy radar plate, or graded B-roll from assets/."""

    def __init__(self, assets_dir: Path | None, use_broll: bool = True):
        self.vig = _vignette()
        self.grid = _grid_overlay()
        self.assets = []
        if use_broll and assets_dir and assets_dir.exists():
            self.assets = sorted(p for p in assets_dir.iterdir()
                                 if p.suffix.lower() in VIDEO_EXT | IMAGE_EXT and not p.name.startswith("."))
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        top, bot = np.array(NAVY, np.float32), np.array(NAVY_DEEP, np.float32)
        base = (top * (1 - yy) + bot * yy) * np.ones((1, W, 1), np.float32)
        base = base * (0.55 + 0.45 * self.vig)
        plate = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")
        plate.paste(self.grid, (0, 0), self.grid)
        self.plate = plate
        self._src = None
        self._src_scene = -1
        self._tint = np.array([0.55, 0.75, 1.15], np.float32)
        self._navy = np.array(NAVY_DEEP, np.float32)

    # B-roll sources
    def _open(self, scene_idx: int):
        self._close()
        self._src_scene = scene_idx
        if not self.assets:
            return
        path = self.assets[scene_idx % len(self.assets)]
        slot = SCENES[scene_idx]
        if path.suffix.lower() in VIDEO_EXT:
            vf = (f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                  f"fps={FPS},format=rgb24")
            proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-stream_loop", "-1", "-i", str(path),
                 "-t", f"{slot.dur + 1:.2f}", "-vf", vf, "-an", "-f", "rawvideo", "-"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=W * H * 3 * 4)
            self._src = ("video", proc)
        else:
            im = Image.open(path).convert("RGB")
            s = max(W * 1.12 / im.width, H * 1.12 / im.height)
            im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
            self._src = ("image", im)

    def _close(self):
        if self._src and self._src[0] == "video":
            proc = self._src[1]
            proc.stdout.close()
            proc.kill()
            proc.wait()
        self._src = None

    def _broll_frame(self, scene_idx: int, lt: float) -> np.ndarray | None:
        if scene_idx != self._src_scene:
            self._open(scene_idx)
        if not self._src:
            return None
        kind, src = self._src
        if kind == "video":
            buf = src.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                self._open(scene_idx)  # restart (should not happen thanks to -stream_loop)
                return None
            return np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        # still image: slow Ken Burns push-in
        im: Image.Image = src
        z = 1.0 + 0.10 * (lt / SCENES[scene_idx].dur)
        cw, ch = W * 1.12 / z, H * 1.12 / z
        cx, cy = im.width / 2 + 20 * math.sin(lt * 0.2), im.height / 2
        box = (cx - cw / 2 * im.width / (W * 1.12), cy - ch / 2 * im.height / (H * 1.12),
               cx + cw / 2 * im.width / (W * 1.12), cy + ch / 2 * im.height / (H * 1.12))
        return np.asarray(im.resize((W, H), Image.BILINEAR, box=box))

    def frame(self, scene_idx: int, lt: float, t: float) -> Image.Image:
        arr = self._broll_frame(scene_idx, lt)
        if arr is None:
            img = self.plate.copy()
        else:
            # dark broadcast grade: desaturate, cool tint, crush, vignette
            f = arr.astype(np.float32)
            g = f.mean(axis=2, keepdims=True)
            f = (0.35 * f + 0.65 * g) * self._tint * 0.40 + self._navy * 0.55
            f *= self.vig
            img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8), "RGB")
            img.paste(self.grid, (0, 0), self.grid)
        d = ImageDraw.Draw(img, "RGBA")
        # slow radar scan band
        y = (t * 140) % (H + 400) - 200
        d.rectangle((0, y, W, y + 160), fill=rgba(CYAN, 7))
        d.line([(0, y + 160), (W, y + 160)], fill=rgba(CYAN, 26), width=2)
        return img

    def close(self):
        self._close()


# ── broadcast chrome ─────────────────────────────────────────────────────
class Chrome:
    def __init__(self, T: dict):
        self.T = T
        self.header = self._header()
        self.ticker_text = T["ticker"] * 3
        self.ticker_w = font("xbold", 30).getlength(T["ticker"])

    def _header(self) -> Image.Image:
        T = self.T
        img = Image.new("RGBA", (W, HEADER_Y1 + 10), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x0, x1 = MARGIN_X - 10, W - MARGIN_X + 10
        d.rectangle((x0, HEADER_Y0, x1, HEADER_Y1), fill=rgba(NAVY_DEEP, 225))
        d.rectangle((x0, HEADER_Y0, x1, HEADER_Y0 + 4), fill=rgba(CYAN, 255))
        d.rectangle((x0, HEADER_Y0 + 4, x0 + 14, 166), fill=rgba(NATO_BLUE, 255))
        text(d, (x0 + 32, HEADER_Y0 + 46), T["channel"], "black", 58, WHITE, anchor="lm")
        text(d, (x0 + 36, HEADER_Y0 + 92), T["tagline"], "mono", 21, CYAN, anchor="lm", spacing=3)
        # desk bar
        d.rectangle((x0, 168, x1, HEADER_Y1), fill=rgba(AMBER, 255))
        d.polygon([(x0, 168), (x0 + 30, 168), (x0 + 14, HEADER_Y1), (x0, HEADER_Y1)], fill=rgba(ALERT_RED, 255))
        desk = "• " + T["desk"]
        sz = 30
        while text_size(desk, "black", sz)[0] > (x1 - x0 - 70) and sz > 18:
            sz -= 1
        text(d, (x0 + 40, (168 + HEADER_Y1) / 2), desk, "black", sz, NAVY_DEEP, anchor="lm")
        return img

    def draw(self, img: Image.Image, t: float, scene_idx: int, lt: float):
        T = self.T
        img.paste(self.header, (0, 0), self.header)
        d = ImageDraw.Draw(img, "RGBA")
        # LIVE badge with blinking dot
        bx1 = W - MARGIN_X
        bw = text_size(T["live"], "black", 28)[0] + 64
        bx0 = bx1 - bw
        d.rectangle((bx0, HEADER_Y0 + 22, bx1, HEADER_Y0 + 72), fill=rgba(ALERT_RED, 255))
        on = (t % 1.0) < 0.6
        d.ellipse((bx0 + 14, HEADER_Y0 + 38, bx0 + 32, HEADER_Y0 + 56), fill=rgba(WHITE, 255 if on else 90))
        text(d, (bx0 + 42, HEADER_Y0 + 47), T["live"], "black", 28, WHITE, anchor="lm")
        # signal bars
        for i in range(5):
            h = 6 + i * 5
            lvl = 0.5 + 0.5 * math.sin(t * 3 + i)
            d.rectangle((bx1 - 90 + i * 16, HEADER_Y0 + 132 - h, bx1 - 80 + i * 16, HEADER_Y0 + 132),
                        fill=rgba(CYAN, 120 + 120 * lvl))

        # scene tag strip
        tag = T["scene_tags"][scene_idx]
        pa = ease_out(prog(lt, 0.0, 0.35))
        idx = f"{scene_idx + 1:02d}/{len(SCENES):02d}"
        iw = text_size(idx, "mono", 22)[0] + 20
        d.rectangle((MARGIN_X, TAG_Y, MARGIN_X + iw, TAG_Y + 40), fill=rgba(CYAN, 255 * pa))
        text(d, (MARGIN_X + 10, TAG_Y + 20), idx, "mono", 22, NAVY_DEEP, pa, anchor="lm")
        shown = tag[: int(len(tag) * clamp(lt / 0.6))]  # typewriter
        text(d, (MARGIN_X + iw + 14, TAG_Y + 20), shown + ("▌" if lt < 0.8 and (t * 4) % 1 < 0.5 else ""),
             "mono", 24, CYAN, 1.0, anchor="lm")
        # scene progress
        slot = SCENES[scene_idx]
        px0, px1 = W - MARGIN_X - 180, W - MARGIN_X
        d.rectangle((px0, TAG_Y + 17, px1, TAG_Y + 23), fill=rgba(CYAN_DIM, 90))
        d.rectangle((px0, TAG_Y + 17, px0 + (px1 - px0) * clamp(lt / slot.dur), TAG_Y + 23), fill=rgba(AMBER, 255))

        # bottom ticker (decorative, sits in the lower UI zone)
        y0, y1 = TICKER_Y, TICKER_Y + 56
        d.rectangle((0, y0, W, y1), fill=rgba(NAVY_DEEP, 230))
        d.line([(0, y0), (W, y0)], fill=rgba(CYAN, 200), width=2)
        off = (t * 150) % self.ticker_w
        lw = text_size(T["ticker_label"], "black", 26)[0] + 40
        f = font("xbold", 30)
        d.text((lw + 20 - off, (y0 + y1) / 2), self.ticker_text, font=f, fill=rgba(WHITE, 235), anchor="lm")
        d.rectangle((0, y0, lw, y1), fill=rgba(ALERT_RED, 255))
        text(d, (20, (y0 + y1) / 2), T["ticker_label"], "black", 26, WHITE, anchor="lm")

    @staticmethod
    def transition(img: Image.Image, t: float):
        """Cyan scan-wipe + flash across each scene cut."""
        for sc in SCENES[1:]:
            dt = t - sc.start
            if -0.18 <= dt <= 0.36:
                d = ImageDraw.Draw(img, "RGBA")
                p = (dt + 0.18) / 0.54
                y = -100 + (H + 200) * p
                flash = max(0.0, 1 - abs(dt) / 0.18)
                if flash > 0:
                    d.rectangle((0, 0, W, H), fill=rgba(WHITE, 60 * flash))
                d.rectangle((0, y - 140, W, y), fill=rgba(CYAN, 30))
                d.rectangle((0, y - 6, W, y + 6), fill=rgba(CYAN, 220))
                d.rectangle((0, y - 1, W, y + 1), fill=rgba(WHITE, 255))


# ── main render loop ─────────────────────────────────────────────────────
def scene_at(t: float) -> int:
    for i, s in enumerate(SCENES):
        if s.start <= t < s.end:
            return i
    return len(SCENES) - 1


def build_scenes(T, cues):
    return [SCENE_CLASSES[s.key](T, s, cues) for s in SCENES]


def compose_frame(t, scenes, bg, chrome, captions) -> Image.Image:
    si = scene_at(t)
    lt = t - SCENES[si].start
    img = bg.frame(si, lt, t)
    scenes[si].draw(img, lt)
    chrome.draw(img, t, si, lt)
    captions.draw(img, t)
    chrome.transition(img, t)
    # fade from / to black at the very edges
    edge = min(prog(t, 0, 0.25), 1 - prog(t, DURATION - 0.35, 0.35))
    if edge < 1:
        ImageDraw.Draw(img, "RGBA").rectangle((0, 0, W, H), fill=(0, 0, 0, int(255 * (1 - edge))))
    return img


def render_video(T, cues, words, audio_wav: Path, out_mp4: Path, assets_dir: Path | None,
                 use_broll: bool = True, crf: int = 19, preset: str = "medium") -> None:
    scenes = build_scenes(T, cues)
    bg = Background(assets_dir, use_broll)
    if bg.assets:
        print(f"  [render] B-roll: {', '.join(p.name for p in bg.assets)}")
    else:
        print("  [render] no B-roll in assets/ — using procedural radar background")
    chrome = Chrome(T)
    captions = CaptionRenderer(words)
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(audio_wav),
           "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-r", str(FPS), "-g", str(FPS * 2),
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
           "-t", f"{DURATION:.3f}", "-movflags", "+faststart", str(out_mp4)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    try:
        for i in range(N_FRAMES):
            t = i / FPS
            img = compose_frame(t, scenes, bg, chrome, captions)
            proc.stdin.write(img.tobytes())
            if i % (FPS * 5) == 0:
                el = time.time() - t0
                print(f"  [render] frame {i:4d}/{N_FRAMES} ({el:5.1f}s elapsed)", flush=True)
    finally:
        bg.close()
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError(f"ffmpeg exited with code {rc}")
    print(f"  [render] {N_FRAMES} frames in {time.time() - t0:.1f}s")


def render_stills(T, cues, words, times: list[float], out_dir: Path, assets_dir, use_broll=True) -> list[Path]:
    scenes = build_scenes(T, cues)
    bg = Background(assets_dir, use_broll)
    chrome = Chrome(T)
    captions = CaptionRenderer(words)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for t in sorted(times):
        p = out_dir / f"still_{t:05.2f}.jpg"
        compose_frame(t, scenes, bg, chrome, captions).save(p, quality=90)
        paths.append(p)
    bg.close()
    return paths
