"""Small Pillow drawing toolkit: easing, alpha text, HUD furniture, flags, icons."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter

from .config import font, rgba, CYAN, AMBER, WHITE, NAVY_DEEP, PANEL, ALERT_RED


# ── timing helpers ───────────────────────────────────────────────────────
def clamp(x: float, a: float = 0.0, b: float = 1.0) -> float:
    return a if x < a else b if x > b else x


def prog(t: float, start: float, dur: float) -> float:
    return clamp((t - start) / dur) if dur > 0 else float(t >= start)


def ease_out(p: float) -> float:
    return 1 - (1 - p) ** 3


def ease_in_out(p: float) -> float:
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_back(p: float) -> float:
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2


# ── text ─────────────────────────────────────────────────────────────────
def text_size(txt: str, style: str, size: int) -> tuple[int, int]:
    l, t, r, b = font(style, size).getbbox(txt)
    return r - l, b - t


def fit_size(txt: str, style: str, size: int, max_w: int, min_size: int = 14) -> int:
    while size > min_size and text_size(txt, style, size)[0] > max_w:
        size -= 2
    return size


def text(d: ImageDraw.ImageDraw, xy, txt: str, style: str, size: int, color, alpha: float = 1.0,
         anchor: str = "la", stroke: int = 0, stroke_color=(0, 0, 0), spacing: int = 0):
    if alpha <= 0.01:
        return
    a = 255 * clamp(alpha)
    f = font(style, size)
    if spacing:
        x, y = xy
        if anchor[0] in "mr":
            total = sum(f.getlength(c) + spacing for c in txt) - spacing
            x -= total / 2 if anchor[0] == "m" else total
        for ch in txt:
            d.text((x, y), ch, font=f, fill=rgba(color, a), anchor="l" + anchor[1],
                   stroke_width=stroke, stroke_fill=rgba(stroke_color, a))
            x += f.getlength(ch) + spacing
        return
    d.text(xy, txt, font=f, fill=rgba(color, a), anchor=anchor,
           stroke_width=stroke, stroke_fill=rgba(stroke_color, a))


# ── HUD furniture ────────────────────────────────────────────────────────
def panel(d, box, alpha=1.0, fill=PANEL, fill_a=200, border=CYAN, border_a=110, radius=6):
    x0, y0, x1, y1 = box
    d.rounded_rectangle(box, radius=radius, fill=rgba(fill, fill_a * alpha),
                        outline=rgba(border, border_a * alpha), width=2)
    brackets(d, box, CYAN, alpha)


def brackets(d, box, color=CYAN, alpha=1.0, L=26, w=4):
    x0, y0, x1, y1 = box
    c = rgba(color, 255 * alpha)
    for (x, y, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(x, y + sy * L), (x, y), (x + sx * L, y)], fill=c, width=w)


def chip(d, xy, label: str, fg=NAVY_DEEP, bg=AMBER, size=28, alpha=1.0, pad=(16, 8), style="black"):
    x, y = xy
    w, h = text_size(label, style, size)
    box = (x, y, x + w + 2 * pad[0], y + size + 2 * pad[1])
    d.rectangle(box, fill=rgba(bg, 255 * alpha))
    text(d, (x + pad[0], y + pad[1] + size / 2), label, style, size, fg, alpha, anchor="lm")
    return box


def glow_layer(pts, color=CYAN, width=4, alpha=1.0, glow=10):
    """Render a glowing polyline to a local RGBA layer -> (layer, x0, y0)."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    pad = glow * 3 + width
    x0, y0 = int(min(xs) - pad), int(min(ys) - pad)
    x1, y1 = int(max(xs) + pad), int(max(ys) + pad)
    layer = Image.new("RGBA", (max(2, x1 - x0), max(2, y1 - y0)), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    local = [(p[0] - x0, p[1] - y0) for p in pts]
    if len(local) >= 2:
        ld.line(local, fill=rgba(color, 170 * alpha), width=width + glow, joint="curve")
        layer = layer.filter(ImageFilter.GaussianBlur(glow / 2))
        ld = ImageDraw.Draw(layer)
        ld.line(local, fill=rgba(color, 255 * alpha), width=width, joint="curve")
        ld.line(local, fill=rgba(WHITE, 150 * alpha), width=max(1, width // 3), joint="curve")
    return layer, x0, y0


def glow_line(img: Image.Image, pts, color=CYAN, width=4, alpha=1.0, glow=10):
    if len(pts) < 2:
        return
    layer, x0, y0 = glow_layer(pts, color, width, alpha, glow)
    img.paste(layer, (x0, y0), layer)


def check_icon(d, cx, cy, s, color, alpha=1.0, w=6):
    c = rgba(color, 255 * alpha)
    d.line([(cx - s * 0.5, cy), (cx - s * 0.12, cy + s * 0.38), (cx + s * 0.55, cy - s * 0.42)],
           fill=c, width=w, joint="curve")


def warn_icon(d, cx, cy, s, color=AMBER, alpha=1.0):
    c = rgba(color, 255 * alpha)
    d.polygon([(cx, cy - s * 0.55), (cx + s * 0.6, cy + s * 0.48), (cx - s * 0.6, cy + s * 0.48)], fill=c)
    text(d, (cx, cy + s * 0.12), "!", "black", int(s * 0.7), NAVY_DEEP, alpha, anchor="mm")


def bell_icon(d, cx, cy, s, color=WHITE, alpha=1.0):
    c = rgba(color, 255 * alpha)
    d.pieslice((cx - s * 0.45, cy - s * 0.55, cx + s * 0.45, cy + s * 0.35), 180, 360, fill=c)
    d.rectangle((cx - s * 0.45, cy - s * 0.1, cx + s * 0.45, cy + s * 0.25), fill=c)
    d.polygon([(cx - s * 0.6, cy + s * 0.32), (cx + s * 0.6, cy + s * 0.32),
               (cx + s * 0.45, cy + s * 0.15), (cx - s * 0.45, cy + s * 0.15)], fill=c)
    d.ellipse((cx - s * 0.13, cy + s * 0.36, cx + s * 0.13, cy + s * 0.58), fill=c)


# ── flags (simplified, drawn procedurally) ──────────────────────────────
_MAPLE = [(0, -1.0), (0.12, -0.72), (0.3, -0.8), (0.24, -0.42), (0.52, -0.6), (0.46, -0.44),
          (0.72, -0.5), (0.62, -0.26), (0.78, -0.2), (0.42, 0.1), (0.48, 0.3), (0.06, 0.22),
          (0.06, 0.62), (-0.06, 0.62), (-0.06, 0.22), (-0.48, 0.3), (-0.42, 0.1), (-0.78, -0.2),
          (-0.62, -0.26), (-0.72, -0.5), (-0.46, -0.44), (-0.52, -0.6), (-0.24, -0.42),
          (-0.3, -0.8), (-0.12, -0.72)]


def flag(img: Image.Image, code: str, box, alpha=1.0):
    x0, y0, x1, y1 = [int(v) for v in box]
    w, h = x1 - x0, y1 - y0
    f = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(f)
    if code == "CA":
        red = (216, 6, 33, 255)
        d.rectangle((0, 0, w, h), fill=(255, 255, 255, 255))
        d.rectangle((0, 0, w // 4, h), fill=red)
        d.rectangle((w - w // 4, 0, w, h), fill=red)
        s = h * 0.36
        d.polygon([(w / 2 + px * s, h / 2 + py * s) for px, py in _MAPLE], fill=red)
    elif code == "DE":
        for i, c in enumerate(((0, 0, 0), (221, 0, 0), (255, 206, 0))):
            d.rectangle((0, i * h / 3, w, (i + 1) * h / 3), fill=c + (255,))
    elif code == "NO":
        d.rectangle((0, 0, w, h), fill=(186, 12, 47, 255))
        cx, cw, bw = w * 0.36, h * 0.25, h * 0.125
        d.rectangle((cx - cw / 2, 0, cx + cw / 2, h), fill=(255, 255, 255, 255))
        d.rectangle((0, h / 2 - cw / 2, w, h / 2 + cw / 2), fill=(255, 255, 255, 255))
        d.rectangle((cx - bw / 2, 0, cx + bw / 2, h), fill=(0, 32, 91, 255))
        d.rectangle((0, h / 2 - bw / 2, w, h / 2 + bw / 2), fill=(0, 32, 91, 255))
    elif code == "EU":
        d.rectangle((0, 0, w, h), fill=(0, 51, 153, 255))
        r, sr = h * 0.33, max(2, h * 0.055)
        for i in range(12):
            a = 2 * math.pi * i / 12
            sx, sy = w / 2 + r * math.sin(a), h / 2 - r * math.cos(a)
            d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 204, 0, 255))
    elif code == "US":
        for i in range(7):
            d.rectangle((0, i * h / 6.5, w, i * h / 6.5 + h / 13), fill=(178, 34, 52, 255))
        d.rectangle((0, h / 13, w, h / 6.5), fill=(255, 255, 255, 255))
        d.rectangle((0, 0, w * 0.42, h * 0.54), fill=(60, 59, 110, 255))
    elif code == "UA":
        d.rectangle((0, 0, w, h / 2), fill=(0, 87, 183, 255))
        d.rectangle((0, h / 2, w, h), fill=(255, 215, 0, 255))
    if alpha < 1:
        a = f.getchannel("A").point(lambda v: int(v * alpha))
        f.putalpha(a)
    img.paste(f, (x0, y0), f)
    ImageDraw.Draw(img, "RGBA").rectangle((x0, y0, x1 - 1, y1 - 1), outline=rgba(WHITE, 120 * alpha), width=1)


def stamp(img: Image.Image, center, lines: list[str], color=ALERT_RED, alpha=1.0, angle=-8, scale=1.0):
    """Rubber-stamp style callout, rotated."""
    sizes = [int(76 * scale), int(26 * scale), int(26 * scale)]
    styles = ["black", "xbold", "xbold"]
    widths = [text_size(l, s, z)[0] for l, s, z in zip(lines, styles, sizes)]
    w = int(max(widths) + 60 * scale)
    h = int(sum(sizes) + 60 * scale)
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle((3, 3, w - 4, h - 4), radius=int(10 * scale), outline=rgba(color, 255 * alpha), width=int(5 * scale))
    d.rounded_rectangle((12, 12, w - 13, h - 13), radius=int(6 * scale), fill=rgba(NAVY_DEEP, 200 * alpha))
    y = 22 * scale
    for l, s, z in zip(lines, styles, sizes):
        text(d, (w / 2, y + z / 2), l, s, z, color if s == "black" else WHITE, alpha, anchor="mm")
        y += z + 4 * scale
    layer = layer.rotate(angle, resample=Image.BICUBIC, expand=True)
    img.paste(layer, (int(center[0] - layer.width / 2), int(center[1] - layer.height / 2)), layer)
