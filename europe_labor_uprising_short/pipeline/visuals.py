"""Frame renderer: draws every frame of the Short with Pillow + numpy.

Layout (1080x1920), kept clear of the YouTube Shorts overlay
(right-side buttons and the bottom ~330 px title/channel area):

    y   0-8     progress bar
    y  70-230   channel header + LIVE badge
    y 300-1330  stage (segment template)
    y 1360-1530 captions
    y 1550-1620 news ticker
"""

from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .content import (CHANNEL_NAME, CHANNEL_TAGLINE, DATELINE, FACTS, HEIGHT,
                      REPORT_TITLE, SEGMENTS, TICKER_ITEMS, TOTAL_DURATION, WIDTH,
                      Segment)

# ------------------------------------------------------------ palette ----
BG_TOP = (10, 12, 22)
BG_BOTTOM = (28, 8, 14)
RED = (230, 57, 70)
RED_DARK = (150, 24, 36)
WHITE = (246, 246, 248)
MUTED = (160, 168, 184)
GOLD = (255, 200, 87)
INK_DARK = (12, 12, 16)

MARGIN = 72
SAFE_RIGHT = WIDTH - 150   # keep text clear of the Shorts action buttons

# -------------------------------------------------------------- fonts ----
FONT_DIRS = [Path("/usr/share/fonts/opentype/inter"), Path("/usr/share/fonts/truetype/dejavu"),
             Path("/usr/share/fonts/truetype/liberation"), Path("/Library/Fonts"),
             Path("C:/Windows/Fonts")]
FONT_CANDIDATES = {
    "black": ["InterDisplay-Black.otf", "Inter-Black.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf"],
    "semi": ["Inter-SemiBold.otf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arial.ttf"],
    "regular": ["Inter-Medium.otf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf", "arial.ttf"],
}


@lru_cache(maxsize=None)
def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    for name in FONT_CANDIDATES[weight]:
        for d in FONT_DIRS:
            p = d / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default(size)


# ------------------------------------------------------------- easing ----
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.7):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def ease_in_out(x):
    x = clamp(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def mix(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


# --------------------------------------------------- static backgrounds ----
class Background:
    def __init__(self, seed: int = 3):
        rng = np.random.default_rng(seed)
        y = np.linspace(0, 1, HEIGHT)[:, None, None]
        grad = np.array(BG_TOP) * (1 - y) + np.array(BG_BOTTOM) * y
        grad = np.broadcast_to(grad, (HEIGHT, WIDTH, 3)).astype(np.float32)
        # vignette
        yy, xx = np.mgrid[0:HEIGHT, 0:WIDTH]
        d = np.sqrt(((xx - WIDTH / 2) / WIDTH) ** 2 + ((yy - HEIGHT * 0.45) / HEIGHT) ** 2)
        self.base = grad * np.clip(1.15 - d * 0.9, 0.35, 1.0)[..., None]
        # diagonal stripe texture (scrolled each frame)
        sw = WIDTH + 400
        sy, sx = np.mgrid[0:HEIGHT, 0:sw]
        self.stripes = ((((sx + sy) // 46) % 2) * 7.0).astype(np.float32)
        # film grain frames
        self.grain = [rng.normal(0, 6.5, (HEIGHT, WIDTH, 1)).astype(np.float32) for _ in range(6)]

    def frame(self, t: float, frame_idx: int, pulse: float) -> np.ndarray:
        off = int((t * 40) % 92)
        img = self.base + self.stripes[:, off:off + WIDTH, None] * np.array([1.0, 0.35, 0.4])
        img = img + pulse * np.array([38.0, 4.0, 8.0])
        img = img + self.grain[frame_idx % len(self.grain)]
        return np.clip(img, 0, 255).astype(np.uint8)


# ----------------------------------------------------- europe network ----
# Approximate lon/lat for a schematic map (illustrative, not to scale).
CITIES = {
    "LISBON": (-9.1, 38.7), "MADRID": (-3.7, 40.4), "BARCELONA": (2.2, 41.4),
    "PARIS": (2.35, 48.85), "BRUSSELS": (4.35, 50.85), "LONDON": (-0.1, 51.5),
    "AMSTERDAM": (4.9, 52.4), "BERLIN": (13.4, 52.5), "PRAGUE": (14.4, 50.1),
    "VIENNA": (16.4, 48.2), "MILAN": (9.2, 45.5), "ROME": (12.5, 41.9),
    "ATHENS": (23.7, 37.98), "WARSAW": (21.0, 52.2), "STOCKHOLM": (18.1, 59.3),
    "DUBLIN": (-6.3, 53.35), "BUDAPEST": (19.0, 47.5),
}
LABELLED = {"PARIS", "ROME", "MADRID"}


def project(lon, lat, box):
    x0, y0, x1, y1 = box
    u = (lon + 11) / (27 + 11)
    v = 1 - (lat - 36) / (61 - 36)
    return x0 + u * (x1 - x0), y0 + v * (y1 - y0)


EDGES = [("LISBON", "MADRID"), ("MADRID", "BARCELONA"), ("BARCELONA", "PARIS"), ("MADRID", "PARIS"),
         ("PARIS", "BRUSSELS"), ("PARIS", "LONDON"), ("LONDON", "DUBLIN"), ("BRUSSELS", "AMSTERDAM"),
         ("AMSTERDAM", "BERLIN"), ("BERLIN", "PRAGUE"), ("PRAGUE", "VIENNA"), ("VIENNA", "BUDAPEST"),
         ("BERLIN", "WARSAW"), ("BERLIN", "STOCKHOLM"), ("PARIS", "MILAN"), ("MILAN", "ROME"),
         ("ROME", "ATHENS"), ("VIENNA", "MILAN"), ("BUDAPEST", "ATHENS"), ("BARCELONA", "ROME")]


# -------------------------------------------------------------- helpers ----
def text_size(draw, txt, f):
    l, t, r, b = draw.textbbox((0, 0), txt, font=f)
    return r - l, b - t


def draw_text_center(draw, cx, y, txt, f, fill, shadow=True):
    w, _ = text_size(draw, txt, f)
    x = cx - w / 2
    if shadow:
        draw.text((x + 4, y + 5), txt, font=f, fill=(0, 0, 0))
    draw.text((x, y), txt, font=f, fill=fill)


def fit_font(draw, txt, weight, max_w, start, min_size=40):
    size = start
    while size > min_size and text_size(draw, txt, font(weight, size))[0] > max_w:
        size -= 4
    return font(weight, size)


def wrap(draw, txt, f, max_w):
    words, lines, cur = txt.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_size(draw, trial, f)[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def overlay(img: Image.Image, layer: Image.Image, alpha: float):
    if alpha <= 0:
        return
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    img.alpha_composite(layer)


def draw_crowd(draw, t, y_base, color, seed=1, count=26, height=150):
    rng = np.random.default_rng(seed)
    xs = np.linspace(-20, WIDTH + 20, count) + rng.uniform(-14, 14, count)
    for i, x in enumerate(xs):
        h = height * rng.uniform(0.7, 1.05)
        bob = math.sin(t * 5 + i * 1.3) * 6
        top = y_base - h + bob
        r = 24 * rng.uniform(0.85, 1.1)
        draw.ellipse([x - r, top - 2 * r, x + r, top], fill=color)
        draw.rounded_rectangle([x - r * 1.3, top + 4, x + r * 1.3, y_base + 40], radius=int(r), fill=color)
        if i % 3 == 0:  # raised fist
            arm_top = top - 2 * r - 60 + math.sin(t * 6 + i) * 10
            draw.line([x + r * 1.1, top + 18, x + r * 1.4, arm_top], fill=color, width=16)
            draw.ellipse([x + r * 1.4 - 16, arm_top - 18, x + r * 1.4 + 16, arm_top + 14], fill=color)
        if i % 7 == 2:  # placard
            px = x - r * 0.4
            draw.line([px, top + 10, px, top - 150], fill=color, width=8)
            draw.rectangle([px - 70, top - 230, px + 70, top - 140], fill=color)


# --------------------------------------------------------------- render ----
class Renderer:
    def __init__(self):
        self.bg = Background()

    # ---- chrome ---------------------------------------------------------
    def chrome(self, img, d, t):
        # progress bar
        d.rectangle([0, 0, WIDTH, 8], fill=(40, 40, 52))
        d.rectangle([0, 0, int(WIDTH * t / TOTAL_DURATION), 8], fill=RED)
        # channel badge
        f1 = font("black", 50)
        w1, _ = text_size(d, CHANNEL_NAME, f1)
        d.rectangle([MARGIN, 76, MARGIN + w1 + 44, 150], fill=RED)
        d.text((MARGIN + 22, 84), CHANNEL_NAME, font=f1, fill=WHITE)
        d.rectangle([MARGIN, 150, MARGIN + w1 + 44, 196], fill=WHITE)
        f2 = font("bold", 28)
        d.text((MARGIN + 22, 157), CHANNEL_TAGLINE, font=f2, fill=INK_DARK)
        # LIVE badge (blinks)
        lx = WIDTH - MARGIN - 190
        d.rounded_rectangle([lx, 84, lx + 190, 142], radius=10, outline=WHITE, width=3)
        on = (math.sin(t * 2 * math.pi * 1.0) > -0.2)
        d.ellipse([lx + 20, 101, lx + 44, 125], fill=RED if on else (90, 30, 34))
        d.text((lx + 58, 90), "LIVE", font=font("black", 40), fill=WHITE)
        f3 = font("semi", 26)
        w3, _ = text_size(d, DATELINE, f3)
        d.text((WIDTH - MARGIN - w3, 160), DATELINE, font=f3, fill=MUTED)
        # report slug
        f4 = font("bold", 30)
        d.text((MARGIN, 232), REPORT_TITLE, font=f4, fill=GOLD)
        d.rectangle([MARGIN, 276, MARGIN + 90, 281], fill=GOLD)

    def ticker(self, d, t):
        y0, y1 = 1555, 1625
        d.rectangle([0, y0, WIDTH, y1], fill=(18, 18, 26))
        d.rectangle([0, y0, 230, y1], fill=RED)
        d.text((24, y0 + 14), "BREAKING", font=font("black", 38), fill=WHITE)
        f = font("bold", 34)
        sep = "   ●   "
        strip = sep.join(TICKER_ITEMS) + sep
        sw, _ = text_size(d, strip, f)
        x = 250 - (t * 170) % sw
        while x < WIDTH:
            d.text((x, y0 + 15), strip, font=f, fill=WHITE)
            x += sw
        d.rectangle([0, y0, 240, y1], fill=RED)
        d.text((24, y0 + 14), "BREAKING", font=font("black", 38), fill=WHITE)

    def captions(self, d, seg: Segment, lt: float):
        words = seg.caption.split()
        chunks, cur = [], []
        for w in words:
            cur.append(w)
            if len(cur) >= 4 or w.endswith((".", ",", ":", "—", "?")):
                chunks.append(" ".join(cur))
                cur = []
        if cur:
            chunks.append(" ".join(cur))
        span = max(0.5, seg.duration - 0.5)
        weights = [len(c) + 6 for c in chunks]
        acc, idx = 0.0, len(chunks) - 1
        for i, wgt in enumerate(weights):
            acc += wgt / sum(weights) * span
            if lt + 0.2 < acc:
                idx = i
                break
        txt = chunks[idx]
        f = fit_font(d, txt, "black", SAFE_RIGHT - MARGIN - 40, 66, 44)
        w, h = text_size(d, txt, f)
        cx = (MARGIN + SAFE_RIGHT) / 2
        y = 1420
        pad = 22
        d.rounded_rectangle([cx - w / 2 - pad, y - 12, cx + w / 2 + pad, y + h + 30], radius=14, fill=(0, 0, 0))
        d.text((cx - w / 2, y), txt, font=f, fill=GOLD if idx == 0 else WHITE)

    # ---- segment templates ---------------------------------------------
    def tpl_hook(self, layer, d, seg, lt):
        draw_crowd(d, lt, 1330, (60, 14, 22), seed=2, height=170)
        lines = seg.data["headline"]
        y = 380
        for i, line in enumerate(lines):
            p = ease_out_back((lt - 0.12 * i) / 0.45)
            if p <= 0:
                y += 230
                continue
            size = int(240 * (0.6 + 0.4 * p))
            f = font("black", size)
            color = RED if line == "STRIKE" else WHITE
            draw_text_center(d, WIDTH / 2, y + (1 - p) * 60, line, f, color)
            y += 230
        p = ease_out((lt - 0.8) / 0.4)
        if p > 0:
            f = font("bold", 42)
            w, _ = text_size(d, seg.data["kicker"], f)
            x = WIDTH / 2 - w / 2
            d.rectangle([x - 24, 1110, x - 24 + (w + 48) * p, 1180], fill=WHITE)
            if p > 0.9:
                d.text((x, 1120), seg.data["kicker"], font=f, fill=INK_DARK)

    def tpl_counter(self, layer, d, seg, lt):
        f1 = FACTS[seg.data["fact"]]
        f2 = FACTS[seg.data["second"]]
        draw_text_center(d, WIDTH / 2, 330, seg.data["title"], font("black", 90), RED)
        d.text((MARGIN, 470), "OCT 17 · UP TO", font=font("bold", 44), fill=MUTED)
        n = int(f1["value"] * ease_out(lt / 2.2))
        draw_text_center(d, WIDTH / 2, 520, f"{n:,}", font("black", 210), WHITE)
        draw_text_center(d, WIDTH / 2, 760, "MARCHED", font("bold", 56), WHITE, shadow=False)
        p = ease_out((lt - 3.0) / 0.6)
        if p > 0:
            y0 = 880 + (1 - p) * 80
            d.rounded_rectangle([MARGIN, y0, WIDTH - MARGIN, y0 + 400], radius=26, fill=(255, 255, 255, int(230 * p)))
            d.text((MARGIN + 40, y0 + 30), "ONE WEEK LATER · OCT 24", font=font("bold", 40), fill=RED_DARK)
            n2 = int(f2["value"] * ease_out((lt - 3.0) / 1.8))
            d.text((MARGIN + 36, y0 + 80), f"{n2:,}", font=font("black", 150), fill=INK_DARK)
            places = int(FACTS["france_oct24_places"]["value"] * ease_out((lt - 3.4) / 1.6))
            d.text((MARGIN + 40, y0 + 270), f"ACROSS {places} CITIES & TOWNS", font=font("black", 52), fill=INK_DARK)

    def tpl_bars(self, layer, d, seg, lt):
        draw_text_center(d, WIDTH / 2, 330, seg.data["title"], font("black", 76), WHITE)
        d.text((MARGIN, 440), "People mobilized, by rally", font=font("regular", 36), fill=MUTED)
        keys = seg.data["facts"]
        vmax = max(FACTS[k]["value"] for k in keys)
        x0, x1 = MARGIN, WIDTH - MARGIN
        y = 520
        bar_h = 70
        for i, k in enumerate(keys):
            fact = FACTS[k]
            p = ease_out((lt - 0.25 * i) / 1.1)
            d.text((x0, y), fact["label"].upper(), font=font("bold", 36), fill=WHITE)
            by = y + 52
            d.rectangle([x0, by, x1, by + bar_h], fill=(255, 255, 255, 18))
            w = (x1 - x0) * fact["value"] / vmax * p
            if w > 2:
                d.rounded_rectangle([x0, by, x0 + max(w, 12), by + bar_h], radius=8, fill=RED)
                d.rectangle([x0, by, x0 + min(w, 8), by + bar_h], fill=RED)  # square at baseline
            val = int(fact["value"] * p)
            label = f"{val:,}" + ("+" if k == "rome" else "")
            if k == "france_oct17":
                label = "UP TO " + label
            vf = font("black", 50)
            vw, _ = text_size(d, label, vf)
            inside = w > vw + 60
            tx = x0 + w - vw - 24 if inside else x0 + w + 20
            d.text((tx, by + 8), label, font=vf, fill=WHITE)
            y += bar_h + 52 + 40
        p = ease_out((lt - 3.2) / 0.5)
        if p > 0:
            y0 = 1185
            d.rounded_rectangle([MARGIN, y0, WIDTH - MARGIN, y0 + 130], radius=20, fill=(255, 200, 87, int(255 * p)))
            draw_text_center(d, WIDTH / 2, y0 + 30, f"{FACTS['countries']['value']} COUNTRIES · ONE WAVE",
                             font("black", 62), INK_DARK, shadow=False)

    def tpl_causes(self, layer, d, seg, lt):
        draw_text_center(d, WIDTH / 2, 330, seg.data["title"], font("black", 100), RED)
        y = 500
        for i, (head, icon, sub) in enumerate(seg.data["items"]):
            p = ease_out((lt - 0.4 - 1.9 * i) / 0.5)
            if p <= 0:
                y += 270
                continue
            x = MARGIN + (1 - p) * -300
            d.rounded_rectangle([x, y, x + WIDTH - 2 * MARGIN, y + 230], radius=24,
                                fill=(255, 255, 255, int(235 * p)))
            cx, cy = x + 110, y + 115
            d.ellipse([cx - 75, cy - 75, cx + 75, cy + 75], fill=RED)
            if icon == "▼":
                d.polygon([(cx - 40, cy - 25), (cx + 40, cy - 25), (cx, cy + 40)], fill=WHITE)
            elif icon == "▲":
                d.polygon([(cx - 40, cy + 25), (cx + 40, cy + 25), (cx, cy - 40)], fill=WHITE)
            else:  # tilted scale: bombs outweigh books
                ang = math.radians(-14 + 4 * math.sin(lt * 3))
                dx, dy = 48 * math.cos(ang), 48 * math.sin(ang)
                d.line([cx - dx, cy - dy, cx + dx, cy + dy], fill=WHITE, width=9)
                d.line([cx, cy, cx, cy + 45], fill=WHITE, width=9)
                d.ellipse([cx - dx - 14, cy - dy, cx - dx + 14, cy - dy + 28], fill=WHITE)
                d.ellipse([cx + dx - 18, cy + dy, cx + dx + 18, cy + dy + 36], fill=WHITE)
            d.text((x + 220, y + 40), head, font=font("black", 72), fill=INK_DARK)
            d.text((x + 222, y + 132), sub.upper(), font=font("bold", 44), fill=RED_DARK)
            y += 270

    def tpl_genz(self, layer, d, seg, lt):
        draw_crowd(d, lt, 1330, (70, 16, 26), seed=5, count=22, height=200)
        p = ease_out_back(lt / 0.5)
        size = int(250 * (1.35 - 0.35 * clamp(p)))
        y = 400
        for i, line in enumerate(seg.data["headline"]):
            f = fit_font(d, line, "black", WIDTH - 2 * MARGIN, size, 80)
            draw_text_center(d, WIDTH / 2, y, line, f, RED if i == 1 else WHITE)
            y += 250
        q = ease_out((lt - 1.0) / 0.4)
        if q > 0:
            f = font("black", 60)
            txt = seg.data["sub"]
            w, _ = text_size(d, txt, f)
            d.rectangle([WIDTH / 2 - w / 2 - 30, 920, WIDTH / 2 - w / 2 - 30 + (w + 60) * q, 1010], fill=GOLD)
            if q > 0.9:
                d.text((WIDTH / 2 - w / 2, 930), txt, font=f, fill=INK_DARK)

    def tpl_question(self, layer, d, seg, lt):
        # Europe network: links light up as a metaphor for coordination
        box = (MARGIN + 30, 760, WIDTH - MARGIN - 30, 1320)
        pts = {c: project(lon, lat, box) for c, (lon, lat) in CITIES.items()}
        grow = clamp((lt - 2.5) / 4.0)
        for i, (a, b) in enumerate(EDGES):
            (xa, ya), (xb, yb) = pts[a], pts[b]
            e = clamp(grow * len(EDGES) - i)
            d.line([xa, ya, xa + (xb - xa) * 1.0, ya + (yb - ya) * 1.0], fill=(255, 255, 255, 40), width=3)
            if e > 0:
                d.line([xa, ya, xa + (xb - xa) * e, ya + (yb - ya) * e], fill=RED + (255,), width=6)
        for c, (x, y) in pts.items():
            r = 13 if c in LABELLED else 9
            pulse = 1 + 0.25 * math.sin(lt * 6 + x)
            d.ellipse([x - r * pulse, y - r * pulse, x + r * pulse, y + r * pulse], fill=GOLD if c in LABELLED else WHITE)
            if c in LABELLED:
                d.text((x + 20, y - 22), c, font=font("bold", 34), fill=GOLD)
        y = 330
        for i, line in enumerate(seg.data["lines"]):
            p = ease_out((lt - 0.35 * i) / 0.4)
            if p <= 0:
                y += 105
                continue
            color = RED if "POWER" in line else (MUTED if line == "↓" else WHITE)
            f = font("black", 96 if line != "↓" else 70)
            if line == "↓":
                cx = WIDTH / 2
                d.polygon([(cx - 30, y + 20), (cx + 30, y + 20), (cx, y + 80)], fill=MUTED)
            else:
                f = fit_font(d, line, "black", WIDTH - 2 * MARGIN, 104, 60)
                draw_text_center(d, WIDTH / 2, y + (1 - p) * 30, line, f, color)
            y += 105

    def tpl_cta(self, layer, d, seg, lt):
        p = ease_out_back(lt / 0.5)
        s = 0.7 + 0.3 * clamp(p)
        f = font("black", int(130 * s))
        draw_text_center(d, WIDTH / 2, 420, "GLOBAL", f, WHITE)
        draw_text_center(d, WIDTH / 2, 560, "NEWS 1.0", f, RED)
        draw_text_center(d, WIDTH / 2, 730, CHANNEL_TAGLINE, font("bold", 54), GOLD)
        q = ease_out((lt - 0.6) / 0.4)
        if q > 0:
            beat = 1 + 0.04 * math.sin(lt * 8)
            bw, bh = 640 * beat, 150 * beat
            cx, cy = WIDTH / 2, 980
            d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], radius=75,
                                fill=RED + (int(255 * q),))
            f = font("black", 76)
            tw, _ = text_size(d, "FOLLOW", f)
            tx = cx - (tw + 60) / 2
            d.text((tx, cy - 46), "FOLLOW", font=f, fill=WHITE)
            ax = tx + tw + 24
            d.polygon([(ax, cy - 24), (ax, cy + 28), (ax + 36, cy + 2)], fill=WHITE)
        draw_text_center(d, WIDTH / 2, 1150, "Workers of Europe: what's your next move?", font("semi", 40), MUTED, shadow=False)

    # ---- frame ------------------------------------------------------------
    def segment_at(self, t: float) -> Segment:
        for s in SEGMENTS:
            if s.start <= t < s.end:
                return s
        return SEGMENTS[-1]

    def render(self, frame_idx: int, fps: int) -> Image.Image:
        t = frame_idx / fps
        seg = self.segment_at(t)
        lt = t - seg.start
        # red flash pulse right at each cut
        since_cut = min(abs(t - s.start) for s in SEGMENTS)
        pulse = max(0.0, 1 - since_cut / 0.25) if t > 0.1 else 0.0
        img = Image.fromarray(self.bg.frame(t, frame_idx, pulse)).convert("RGBA")

        stage = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        sd = ImageDraw.Draw(stage)
        getattr(self, f"tpl_{seg.kind}")(stage, sd, seg, lt)
        # segment in/out fades
        alpha = clamp(lt / 0.18) * clamp((seg.duration - lt) / 0.2) if seg.key != "cta" else clamp(lt / 0.18)
        overlay(img, stage, alpha)

        d = ImageDraw.Draw(img)
        self.chrome(img, d, t)
        self.captions(d, seg, lt)
        self.ticker(d, t)
        # wipe bar at cuts
        if pulse > 0:
            d.rectangle([0, 0, int(WIDTH * pulse), 18], fill=WHITE)
        return img.convert("RGB")
