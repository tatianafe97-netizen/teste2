"""Shared drawing toolkit: fonts, text, panels, header, ticker, captions,
generated backdrop, photo Ken Burns + vignette."""
import math
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import config as C

# --------------------------------------------------------------------------- #
# Fonts
# --------------------------------------------------------------------------- #
FONT_FILES = {
    "black": "InterDisplay-Black.otf",
    "xbold": "Inter-ExtraBold.otf",
    "bold": "Inter-Bold.otf",
    "semi": "Inter-SemiBold.otf",
    "medium": "Inter-Medium.otf",
    "mono": "JetBrainsMono-Bold.ttf",
    "monox": "JetBrainsMono-ExtraBold.ttf",
}
FALLBACKS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/Library/Fonts/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"]


@lru_cache(maxsize=None)
def font(name, size):
    path = C.FONTS / FONT_FILES[name]
    for p in [path, *FALLBACKS]:
        try:
            return ImageFont.truetype(str(p), size)
        except OSError:
            continue
    return ImageFont.load_default(size)


# --------------------------------------------------------------------------- #
# Easing / small math
# --------------------------------------------------------------------------- #
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, start, dur):
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x, s=1.4):
    x -= 1
    return x * x * ((s + 1) * x + s) + 1


def pulse(t, hz=1.2, lo=0.0, hi=1.0):
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * hz * t))


def rgba(c, a=255):
    return (*c[:3], int(a))


def lerp_color(a, b, x):
    return tuple(int(a[i] + (b[i] - a[i]) * x) for i in range(3))


# --------------------------------------------------------------------------- #
# Text
# --------------------------------------------------------------------------- #
def text_w(text, f, tracking=0):
    if not tracking:
        return f.getlength(text)
    return sum(f.getlength(ch) for ch in text) + tracking * (len(text) - 1)


def draw_text(img_or_draw, xy, text, f, fill=C.WHITE, anchor="ls", tracking=0,
              shadow=None, alpha=255):
    """anchor: horizontal l/m/r + vertical (Pillow codes: 'a' ascender, 'm' middle,
    's' baseline). Tracking drawn char-by-char."""
    d = img_or_draw if isinstance(img_or_draw, ImageDraw.ImageDraw) else ImageDraw.Draw(img_or_draw)
    x, y = xy
    w = text_w(text, f, tracking)
    if anchor[0] == "m":
        x -= w / 2
    elif anchor[0] == "r":
        x -= w
    va = "l" + anchor[1]
    col = rgba(fill, alpha) if len(fill) == 3 else fill
    if shadow:
        sx, sy, sc = shadow
        _draw_run(d, (x + sx, y + sy), text, f, rgba(sc, alpha * sc[3] / 255 if len(sc) > 3 else alpha * 0.6), va, tracking)
    _draw_run(d, (x, y), text, f, col, va, tracking)
    return w


def _draw_run(d, xy, text, f, fill, va, tracking):
    x, y = xy
    if not tracking:
        d.text((x, y), text, font=f, fill=fill, anchor=va)
        return
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill, anchor=va)
        x += f.getlength(ch) + tracking


def fit_font(text, name, size, max_w, tracking=0, min_size=18):
    while size > min_size and text_w(text, font(name, size), tracking) > max_w:
        size -= 2
    return font(name, size)


def wrap(text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if f.getlength(trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------- #
# Panels
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=256)
def _shadow(w, h, radius, a):
    sh = Image.new("RGBA", (w + 60, h + 60), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((30, 38, w + 30, h + 30), radius, fill=(0, 0, 0, a))
    return sh.filter(ImageFilter.GaussianBlur(14))


def panel(layer, box, alpha=232, radius=18, accent=C.RED, outline=C.NAVY_LINE, fill=C.NAVY):
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = [int(v) for v in box]
    # soft drop shadow (cached: blurring every panel every frame is slow)
    layer.alpha_composite(_shadow(x1 - x0, y1 - y0, radius, int(alpha * 0.55) // 8 * 8), (x0 - 30, y0 - 30))
    d.rounded_rectangle(box, radius, fill=rgba(fill, alpha), outline=rgba(outline, 200), width=2)
    if accent:
        d.rounded_rectangle((x0, y0, x1, y0 + 6), 3, fill=rgba(accent, 255))


def tag(layer, xy, text, bg=C.RED, fg=C.WHITE, size=26, pad=(16, 9), tracking=2, alpha=255):
    d = ImageDraw.Draw(layer)
    f = font("xbold", size)
    w = text_w(text, f, tracking)
    x, y = xy
    h = size + pad[1] * 2
    d.rounded_rectangle((x, y, x + w + pad[0] * 2, y + h), 6, fill=rgba(bg, alpha))
    draw_text(d, (x + pad[0], y + h / 2 + 1), text, f, fg, anchor="lm", tracking=tracking, alpha=alpha)
    return w + pad[0] * 2, h


def section_title(layer, t, kicker, title, y=C.CONTENT_TOP + 8, color=C.RED):
    """Animated scene heading: red kicker tag + big white title sliding in."""
    a = ease_out(prog(t, 0.0, 0.45))
    x = C.MARGIN - 40 * (1 - a)
    tag(layer, (x, y), kicker, bg=color, alpha=255 * a)
    f = fit_font(title, "black", 64, C.W - 2 * C.MARGIN)
    draw_text(layer, (C.MARGIN + 30 * (1 - ease_out(prog(t, 0.1, 0.5))), y + 116), title, f,
              C.WHITE, anchor="ls", alpha=255 * ease_out(prog(t, 0.1, 0.5)),
              shadow=(0, 3, (0, 0, 0, 150)))


# --------------------------------------------------------------------------- #
# Generated backdrop + vignette
# --------------------------------------------------------------------------- #
def vignette_mask(strength=0.85):
    yy, xx = np.mgrid[0:C.H, 0:C.W].astype(np.float32)
    nx, ny = (xx / C.W - 0.5) * 2, (yy / C.H - 0.5) * 2
    r = np.sqrt(nx ** 2 * 1.0 + ny ** 2 * 0.75)
    v = np.clip((r - 0.35) / 0.95, 0, 1) ** 1.6 * strength
    return v


def generated_backdrop():
    yy, xx = np.mgrid[0:C.H, 0:C.W].astype(np.float32)
    # diagonal navy gradient with a cool glow behind the content area
    g = np.zeros((C.H, C.W, 3), np.float32)
    base_a, base_b = np.array(C.NAVY_DEEP, np.float32), np.array(C.NAVY, np.float32)
    mix = np.clip(1 - (yy / C.H) * 0.9 - (xx / C.W) * 0.1, 0, 1)[..., None]
    g[:] = base_a + (base_b - base_a) * mix * 0.9
    glow = np.exp(-(((xx - C.W * 0.5) / 700) ** 2 + ((yy - 780) / 650) ** 2))[..., None]
    g += np.array([18, 40, 90], np.float32) * glow * 0.55
    # fine broadcast grid
    grid = ((xx % 60) < 1.2) | ((yy % 60) < 1.2)
    g[grid] += 7
    # film grain (static) keeps gradients from banding in H.264
    g += np.random.default_rng(3).normal(0, 2.2, g.shape)
    g *= (1 - vignette_mask(0.7))[..., None]
    return Image.fromarray(np.clip(g, 0, 255).astype(np.uint8), "RGB").convert("RGBA")


class KenBurns:
    """Cover-fit photo with slow zoom/pan, darkened and vignetted so broadcast
    graphics stay readable on top."""

    def __init__(self, path, seed=0, zoom=(1.04, 1.14), darken=0.42):
        img = Image.open(path).convert("RGB")
        scale = max(C.W / img.width, C.H / img.height) * zoom[1]
        self.src = img.resize((math.ceil(img.width * scale), math.ceil(img.height * scale)), Image.LANCZOS)
        self.zoom = zoom
        rng = np.random.default_rng(seed)
        self.pan = rng.uniform(-1, 1, 2)
        self.darken = darken
        v = vignette_mask(0.9)
        shade = (1 - v) * darken
        # blue-ish broadcast grade: keep a touch of navy in the shadows
        self.mul = Image.fromarray(np.clip(shade * 255, 0, 255).astype(np.uint8), "L")
        self.tint = Image.new("RGB", (C.W, C.H), C.NAVY_DEEP)

    def frame(self, x):
        """x in [0,1] across the scene."""
        z = self.zoom[0] + (self.zoom[1] - self.zoom[0]) * ease_in_out(x)
        sw, sh = self.src.size
        cw, ch = C.W * self.zoom[1] / z, C.H * self.zoom[1] / z
        cx = sw / 2 + self.pan[0] * (sw - cw) / 2 * (x - 0.5)
        cy = sh / 2 + self.pan[1] * (sh - ch) / 2 * (x - 0.5)
        box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
        im = self.src.resize((C.W, C.H), Image.BICUBIC, box=box)
        im = Image.composite(im, self.tint, self.mul)
        return im.convert("RGBA")


# --------------------------------------------------------------------------- #
# Header + breaking strip
# --------------------------------------------------------------------------- #
class Header:
    def __init__(self):
        self.base = Image.new("RGBA", (C.W, C.HEADER_Y + C.HEADER_H + C.BREAKING_H + 12), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.base)
        y0, y1 = C.HEADER_Y, C.HEADER_Y + C.HEADER_H
        # navy bar with subtle vertical gradient
        for i in range(C.HEADER_H):
            c = lerp_color(C.NAVY_MID, C.NAVY_DEEP, i / C.HEADER_H)
            d.line((0, y0 + i, C.W, y0 + i), fill=rgba(c, 245))
        d.line((0, y0, C.W, y0), fill=rgba(C.NAVY_LINE), width=2)
        # logo block
        lx, ly, ls = C.MARGIN, y0 + 22, C.HEADER_H - 44
        d.rounded_rectangle((lx, ly, lx + ls, ly + ls), 14, fill=rgba(C.RED))
        draw_text(d, (lx + ls / 2, ly + ls * 0.47), "GN", font("black", 50), anchor="mm")
        draw_text(d, (lx + ls / 2, ly + ls * 0.83), "1.0", font("monox", 24), anchor="mm")
        tx = lx + ls + 26
        draw_text(d, (tx, y0 + 80), C.CHANNEL, font("black", 62), anchor="ls")
        draw_text(d, (tx + 2, y0 + 120), C.CHANNEL_TAGLINE, font("bold", 24), C.MUTED,
                  anchor="ls", tracking=6)
        self.y_strip = y1
        self.f_strip = fit_font(C.BREAKING_TAG, "black", 36, C.W - 2 * C.MARGIN - 80, tracking=1)
        self.f_live = font("xbold", 26)

    def draw(self, frame, t):
        frame.alpha_composite(self.base)
        d = ImageDraw.Draw(frame)
        # LIVE pill (pulsing dot)
        px1, py = C.W - C.MARGIN, C.HEADER_Y + 40
        pw = 128
        d.rounded_rectangle((px1 - pw, py, px1, py + 46), 23, outline=rgba(C.WHITE, 210), width=2,
                            fill=rgba(C.NAVY_DEEP, 160))
        a = pulse(t, 1.1, 0.25, 1.0)
        d.ellipse((px1 - pw + 18, py + 14, px1 - pw + 36, py + 32), fill=rgba(C.RED, 255 * a))
        draw_text(d, (px1 - pw + 48, py + 24), "LIVE", self.f_live, anchor="lm", tracking=3)

        # Breaking strip: red bar whose brightness breathes + periodic shine sweep
        y0, y1 = self.y_strip, self.y_strip + C.BREAKING_H
        br = pulse(t, 0.9, 0.0, 1.0)
        col = lerp_color(C.RED_DARK, C.RED, 0.55 + 0.45 * br)
        d.rectangle((0, y0, C.W, y1), fill=rgba(col))
        sweep = ((t * 0.45) % 1.0) * (C.W + 600) - 300
        shine = Image.new("RGBA", (220, C.BREAKING_H), (255, 255, 255, 0))
        sd = ImageDraw.Draw(shine)
        for i in range(220):
            sd.line((i, 0, i, C.BREAKING_H), fill=(255, 255, 255, int(46 * math.sin(math.pi * i / 220))))
        frame.alpha_composite(shine, (int(sweep), y0))
        d.line((0, y1, C.W, y1), fill=rgba((255, 90, 90)), width=2)
        # pulsing dot
        cy = (y0 + y1) / 2
        r = 9 + 5 * pulse(t, 1.4)
        d.ellipse((C.MARGIN + 14 - r, cy - r, C.MARGIN + 14 + r, cy + r),
                  fill=rgba(C.WHITE, 90 + 120 * (1 - pulse(t, 1.4))))
        d.ellipse((C.MARGIN + 6, cy - 8, C.MARGIN + 22, cy + 8), fill=rgba(C.WHITE))
        draw_text(d, (C.MARGIN + 46, cy + 2), C.BREAKING_TAG, self.f_strip, anchor="lm", tracking=1)


# --------------------------------------------------------------------------- #
# Ticker
# --------------------------------------------------------------------------- #
class Ticker:
    SPEED = 150  # px/s

    def __init__(self, items):
        f = font("bold", 30)
        sep = "   \u25C6   "
        text = sep.join(items) + sep
        w = int(text_w(text, f)) + 1
        self.strip_w = w
        self.strip = Image.new("RGBA", (w * 2, C.TICKER_H), (0, 0, 0, 0))
        d = ImageDraw.Draw(self.strip)
        for k in range(2):
            draw_text(d, (k * w, C.TICKER_H / 2 + 1), text, f, C.OFFWHITE, anchor="lm")
        self.label_w = 190

    def draw(self, frame, t, alpha=1.0):
        y = C.TICKER_Y
        d = ImageDraw.Draw(frame)
        d.rectangle((0, y, C.W, y + C.TICKER_H), fill=rgba(C.NAVY_DEEP, 235))
        d.line((0, y, C.W, y), fill=rgba(C.NAVY_LINE), width=2)
        off = int((t * self.SPEED) % self.strip_w)
        crop = self.strip.crop((off, 0, off + C.W - self.label_w, C.TICKER_H))
        frame.alpha_composite(crop, (self.label_w, y))
        d.rectangle((0, y, self.label_w, y + C.TICKER_H), fill=rgba(C.RED))
        d.polygon([(self.label_w, y), (self.label_w + 22, y), (self.label_w, y + C.TICKER_H)], fill=rgba(C.RED))
        draw_text(d, (self.label_w / 2 + 6, y + C.TICKER_H / 2 + 1), "LATEST", font("black", 30),
                  anchor="mm", tracking=2)


# --------------------------------------------------------------------------- #
# Captions
# --------------------------------------------------------------------------- #
class Captions:
    MAX_W = 900
    FONT = ("xbold", 60)

    def __init__(self, phrases):
        self.phrases = phrases
        self.f = font(*self.FONT)
        self._cache = {}

    def _layout(self, idx):
        if idx in self._cache:
            return self._cache[idx]
        p = self.phrases[idx]
        space = self.f.getlength(" ")
        lines, cur, cur_w = [], [], 0
        for tk in p["tokens"]:
            w = self.f.getlength(tk["text"])
            if cur and cur_w + space + w > self.MAX_W - 60:
                lines.append(cur)
                cur, cur_w = [], 0
            cur.append({**tk, "w": w})
            cur_w += (space if len(cur) > 1 else 0) + w
        if cur:
            lines.append(cur)
        self._cache[idx] = (lines, space)
        return lines, space

    def draw(self, frame, t):
        idx = next((i for i, p in enumerate(self.phrases) if p["start"] <= t < p["end"]), None)
        if idx is None:
            return
        p = self.phrases[idx]
        lines, space = self._layout(idx)
        lh = 78
        box_h = lh * len(lines) + 34
        widths = [sum(tk["w"] for tk in ln) + space * (len(ln) - 1) for ln in lines]
        box_w = max(widths) + 64
        a = ease_out(prog(t, p["start"], 0.12))
        cy = C.CAPTION_CENTER_Y
        x0, y0 = (C.W - box_w) / 2, cy - box_h / 2 + 10 * (1 - a)
        d = ImageDraw.Draw(frame)
        d.rounded_rectangle((x0, y0, x0 + box_w, y0 + box_h), 16, fill=(4, 8, 20, int(196 * a)))
        d.rectangle((x0, y0 + 14, x0 + 6, y0 + box_h - 14), fill=rgba(C.RED, 255 * a))
        spoken = [tk for ln in lines for tk in ln if tk["start"] <= t]
        current = spoken[-1] if spoken and t < spoken[-1]["end"] + 0.25 else None
        for li, ln in enumerate(lines):
            x = (C.W - widths[li]) / 2
            base = y0 + 17 + lh * li + lh * 0.5
            for tk in ln:
                active = tk is current
                said = t >= tk["start"]
                col = C.WHITE if said else (205, 212, 226)
                # heavy stroke for legibility on any background
                d.text((x, base), tk["text"], font=self.f, anchor="lm",
                       fill=rgba(col, 255 * a), stroke_width=3, stroke_fill=(0, 0, 0, int(200 * a)))
                if active:
                    d.rounded_rectangle((x, base + 34, x + tk["w"], base + 40), 3, fill=rgba(C.RED, 255 * a))
                x += tk["w"] + space


def build_phrases(words, script_blocks, subs):
    """Align display tokens (with punctuation) from the script onto edge-tts word
    timings, apply number substitutions, then group into short caption phrases."""
    import re
    norm = lambda s: re.sub(r"[^A-Za-z0-9]", "", s).lower()
    phrases = []
    for bi, block in enumerate(script_blocks):
        bw = [w for w in words if w["block"] == bi]
        toks, wi = [], 0
        for raw in block["text"].split():
            need, got, chunk = len(norm(raw)), 0, []
            while wi < len(bw) and got < need:
                chunk.append(bw[wi])
                got += len(norm(bw[wi]["text"]))
                wi += 1
            if chunk:
                toks.append({"text": raw, "start": chunk[0]["start"], "end": chunk[-1]["end"]})
            elif toks:
                toks[-1]["text"] += " " + raw
        # number substitutions ("thirty-five thousand" -> "35,000")
        for src, dst in subs:
            parts = src.split()
            i = 0
            while i <= len(toks) - len(parts):
                seg = toks[i:i + len(parts)]
                if [norm(s["text"]) for s in seg] == [norm(p) for p in parts]:
                    trail = re.match(r".*?([.,;:!?]*)$", seg[-1]["text"]).group(1)
                    toks[i:i + len(parts)] = [{"text": dst + trail, "start": seg[0]["start"], "end": seg[-1]["end"]}]
                i += 1
        # group
        cur = []
        for k, tk in enumerate(toks):
            cur.append(tk)
            chars = sum(len(x["text"]) + 1 for x in cur)
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            gap = (nxt["start"] - tk["end"]) if nxt else 9
            hard = tk["text"][-1] in ".!?:;"
            soft = tk["text"][-1] == ","
            if (nxt is None or hard or gap > 0.3 or (soft and chars > 12) or chars > 22
                    or (len(cur) >= 5)):
                phrases.append(cur)
                cur = []
    out = []
    for i, ph in enumerate(phrases):
        start = ph[0]["start"] - 0.06
        end = ph[-1]["end"] + 0.35
        if i + 1 < len(phrases):
            end = min(end, phrases[i + 1][0]["start"] - 0.06)
        out.append({"start": start, "end": end, "tokens": ph,
                    "text": " ".join(t["text"] for t in ph)})
    return out
