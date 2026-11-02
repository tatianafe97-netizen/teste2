"""Situation-room graphics engine: Pillow + matplotlib frames for the Iran War Short."""
import datetime as dt
import glob
import math
import os
import re
from functools import lru_cache

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

W, H = 1080, 1920
FPS = 30

# Palette: dark slate, radar amber, alert red, clean white telemetry.
SLATE = (12, 18, 26)
SLATE2 = (20, 29, 40)
PANEL_BG = (16, 24, 34)
GRID = (44, 60, 78)
WATER = (15, 31, 46)
LAND = (33, 42, 52)
AMBER = (255, 176, 0)
AMBER_D = (150, 100, 0)
RED = (232, 38, 46)
WHITE = (238, 243, 248)
MUTED = (128, 146, 164)
STEEL = (120, 170, 220)

PANEL = (40, 370, 1000, 860)  # x, y, w, h of the main graphic area

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
_FONTS = {
    "bold": ["DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"],
    "reg": ["DejaVuSans.ttf", "LiberationSans-Regular.ttf"],
    "mono": ["DejaVuSansMono-Bold.ttf", "LiberationMono-Bold.ttf"],
    "cond": ["DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf"],
}


@lru_cache(maxsize=None)
def font(size, kind="bold"):
    for name in _FONTS[kind]:
        for root in (FONT_DIR, "/usr/share/fonts/truetype/liberation"):
            p = os.path.join(root, name)
            if os.path.exists(p):
                return ImageFont.truetype(p, size)
    try:
        return ImageFont.truetype(matplotlib.font_manager.findfont("DejaVu Sans"), size)
    except Exception:
        return ImageFont.load_default()


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def prog(t, start, dur):
    return ease((t - start) / dur)


def rgba(c, a):
    return (c[0], c[1], c[2], int(clamp(a) * 255))


def brackets(d, box, color, length=34, width=4):
    x0, y0, x1, y1 = box
    for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.line([(cx, cy), (cx + sx * length, cy)], fill=color, width=width)
        d.line([(cx, cy), (cx, cy + sy * length)], fill=color, width=width)


def partial_polyline(pts, frac):
    """Return the leading `frac` (0-1) of a polyline by length."""
    if frac <= 0:
        return []
    segs = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total, target = sum(segs), sum(segs) * clamp(frac)
    out, acc = [pts[0]], 0.0
    for i, s in enumerate(segs):
        if acc + s >= target:
            r = (target - acc) / s if s else 0
            out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * r,
                        pts[i][1] + (pts[i + 1][1] - pts[i][1]) * r))
            return out
        out.append(pts[i + 1])
        acc += s
    return out


def dashed(d, pts, color, width=4, dash=18, gap=12, offset=0.0):
    """Dashed polyline with an animated phase."""
    period = dash + gap
    pos = -offset % period - period
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        seg = math.dist(pts[i], pts[i + 1])
        if seg == 0:
            continue
        ux, uy = (x1 - x0) / seg, (y1 - y0) / seg
        s = pos
        while s < seg:
            a, b = max(s, 0), min(s + dash, seg)
            if b > a:
                d.line([(x0 + ux * a, y0 + uy * a), (x0 + ux * b, y0 + uy * b)], fill=color, width=width)
            s += period
        pos = s - period - seg  # carry the dash phase into the next segment


def text_box(d, xy, text, f, fg, bg, pad=(14, 8), anchor="la"):
    x, y = xy
    l, t, r, b = d.textbbox((x, y), text, font=f, anchor=anchor)
    d.rectangle([l - pad[0], t - pad[1], r + pad[0], b + pad[1]], fill=bg)
    d.text((x, y), text, font=f, fill=fg, anchor=anchor)
    return (l - pad[0], t - pad[1], r + pad[0], b + pad[1])


# --------------------------------------------------------------------------- geography
# Simplified, hand-digitised coastlines (lon, lat) — schematic broadcast map, not for navigation.
IRAN = [(47.5, 31.5), (47.5, 30.6), (48.0, 30.4), (48.6, 30.0), (49.2, 30.1), (50.1, 29.9), (50.6, 29.2),
        (50.85, 28.9), (51.3, 28.0), (51.6, 27.85), (52.5, 27.4), (53.5, 26.9), (54.4, 26.6), (54.9, 26.55),
        (55.6, 26.75), (56.1, 27.05), (56.3, 27.18), (56.9, 27.05), (57.3, 26.4), (57.6, 25.8), (57.8, 25.67),
        (58.5, 25.6), (59.3, 25.4), (60.5, 25.3), (60.5, 31.5)]
ARABIA = [(47.5, 29.8), (48.0, 29.6), (48.2, 29.3), (48.4, 28.6), (48.9, 27.9), (49.6, 27.1), (50.15, 26.7),
          (50.2, 26.3), (50.05, 25.9), (50.4, 25.3), (50.75, 24.75), (50.85, 24.85), (50.95, 25.5), (51.2, 26.15),
          (51.55, 25.95), (51.6, 25.3), (51.45, 24.65), (51.6, 24.25), (52.5, 24.2), (53.5, 24.1), (54.4, 24.35),
          (54.9, 24.9), (55.5, 25.4), (56.0, 25.85), (56.1, 26.05), (56.25, 26.3), (56.37, 26.38), (56.45, 26.2),
          (56.4, 25.9), (56.35, 25.4), (56.4, 24.9), (56.7, 24.3), (57.3, 23.9), (58.2, 23.65), (58.8, 23.4),
          (59.3, 22.8), (60.5, 22.3), (60.5, 21.0), (47.5, 21.0)]
QESHM = [(55.3, 26.62), (55.7, 26.8), (56.1, 26.98), (56.25, 26.93), (55.9, 26.72), (55.5, 26.58)]
BAHRAIN = [(50.45, 26.25), (50.62, 26.22), (50.6, 25.8), (50.47, 25.85)]


class GeoMap:
    """matplotlib-rendered base map + lon/lat -> pixel projection."""

    def __init__(self, extent, size, grid_step=1.0):
        self.lon0, self.lon1, self.lat0, self.lat1 = extent
        self.w, self.h = size
        fig = plt.figure(figsize=(self.w / 100, self.h / 100), dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(self.lon0, self.lon1)
        ax.set_ylim(self.lat0, self.lat1)
        ax.axis("off")
        c = lambda col, a=1.0: (col[0] / 255, col[1] / 255, col[2] / 255, a)  # noqa: E731
        ax.add_patch(plt.Rectangle((self.lon0, self.lat0), self.lon1 - self.lon0, self.lat1 - self.lat0,
                                   color=c(WATER), zorder=0))
        # bathymetry-style contour rings offset from the coasts
        for poly in (IRAN, ARABIA):
            xs, ys = zip(*poly)
            for k, lw in ((0.18, 0.8), (0.36, 0.6)):
                ax.plot(xs, ys, color=c(STEEL, 0.10), lw=lw + 10 * k, zorder=1, solid_joinstyle="round")
        for poly in (IRAN, ARABIA, QESHM, BAHRAIN):
            xs, ys = zip(*poly)
            ax.fill(xs, ys, color=c(LAND), zorder=2)
            ax.plot(list(xs) + [xs[0]], list(ys) + [ys[0]], color=c(AMBER, 0.55), lw=1.6, zorder=3)
        g = grid_step
        for lon in np.arange(math.ceil(self.lon0 / g) * g, self.lon1, g):
            ax.axvline(lon, color=c(GRID, 0.6), lw=0.8, zorder=4, ls=(0, (4, 4)))
        for lat in np.arange(math.ceil(self.lat0 / g) * g, self.lat1, g):
            ax.axhline(lat, color=c(GRID, 0.6), lw=0.8, zorder=4, ls=(0, (4, 4)))
        fig.canvas.draw()
        buf = np.asarray(fig.canvas.buffer_rgba()).copy()
        plt.close(fig)
        self.image = Image.fromarray(buf, "RGBA")

    def px(self, lon, lat):
        return ((lon - self.lon0) / (self.lon1 - self.lon0) * self.w,
                (self.lat1 - lat) / (self.lat1 - self.lat0) * self.h)


# --------------------------------------------------------------------------- background / B-roll
IMG_EXT = (".jpg", ".jpeg", ".png")
VID_EXT = (".mp4", ".mov", ".m4v")


def _fill_crop(img, size=(W, H), zoom=1.0, pan=(0.5, 0.5)):
    sw, sh = img.size
    scale = max(size[0] / sw, size[1] / sh) * zoom
    nw, nh = int(sw * scale + 0.5), int(sh * scale + 0.5)
    img = img.resize((nw, nh), Image.BILINEAR)
    x = int((nw - size[0]) * pan[0])
    y = int((nh - size[1]) * pan[1])
    return img.crop((x, y, x + size[0], y + size[1]))


def _vignette():
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.58)) ** 2)
    return np.clip(1.05 - 0.75 * r ** 2.2, 0.18, 1.0)[..., None]


class Background:
    """B-roll hook: any .mp4/.jpg in assets/ is darkened, tinted and vignetted behind the graphics."""

    def __init__(self, assets_dir, n_scenes):
        self.vig = _vignette()
        files = sorted(f for f in glob.glob(os.path.join(assets_dir, "*"))
                       if f.lower().endswith(IMG_EXT + VID_EXT))
        self.sources = []
        for f in files:
            try:
                if f.lower().endswith(VID_EXT):
                    from moviepy import VideoFileClip
                    clip = VideoFileClip(f, audio=False)
                    self.sources.append(("video", clip))
                else:
                    self.sources.append(("image", Image.open(f).convert("RGB")))
                print(f"  B-roll: {os.path.basename(f)}")
            except Exception as exc:
                print(f"  B-roll skipped ({os.path.basename(f)}): {exc}")
        self.n_scenes = n_scenes
        self.fallback = self._synthetic()

    def _synthetic(self):
        g = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        top, bot = np.array(SLATE2, np.float32), np.array(SLATE, np.float32)
        arr = np.broadcast_to(top * (1 - g) + bot * g, (H, W, 3)).copy()
        img = Image.fromarray(arr.astype(np.uint8))
        d = ImageDraw.Draw(img)
        for x in range(0, W, 60):
            d.line([(x, 0), (x, H)], fill=(24, 34, 46), width=1)
        for y in range(0, H, 60):
            d.line([(0, y), (W, y)], fill=(24, 34, 46), width=1)
        arr = np.asarray(img).astype(np.float32) * self.vig
        return Image.fromarray(arr.astype(np.uint8)).convert("RGBA")

    def frame(self, t, scene_idx, scene_t):
        if not self.sources:
            return self.fallback.copy()
        kind, src = self.sources[scene_idx % len(self.sources)]
        if kind == "video":
            fr = src.get_frame(scene_t % max(src.duration - 0.05, 0.1))
            img = _fill_crop(Image.fromarray(fr.astype(np.uint8)))
        else:  # slow Ken Burns push-in
            img = _fill_crop(src, zoom=1.0 + 0.012 * scene_t, pan=(0.5, 0.45))
        arr = np.asarray(img).astype(np.float32)
        gray = arr.mean(axis=2, keepdims=True)
        arr = gray * 0.55 + arr * 0.45                      # partial desaturation
        arr = arr * 0.34 + np.array(SLATE, np.float32) * 0.66 * 0.9   # dark slate broadcast tint
        arr *= self.vig
        return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")


def scanlines():
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 4):
        d.line([(0, y), (W, y)], fill=(0, 0, 0, 22))
    return img


# --------------------------------------------------------------------------- captions
def attach_punctuation(words, script_text):
    """Mark words followed by punctuation in the original script (for natural caption breaks)."""
    pos, low = 0, script_text.lower()
    for w in words:
        token = w["text"].lower()
        i = low.find(token, pos)
        if i < 0:
            w["punct"] = ""
            continue
        j = i + len(token)
        m = re.match(r"[.,:;?!]+", script_text[j:])
        w["punct"] = m.group(0) if m else ""
        pos = j
    return words


def build_caption_chunks(words, max_words=4, max_chars=24):
    chunks, cur = [], []
    for w in words:
        cur.append(w)
        text = " ".join(x["text"] for x in cur)
        if len(cur) >= max_words or len(text) >= max_chars or w.get("punct"):
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else c[-1]["end"] + 0.6
        same_scene = i + 1 < len(chunks) and chunks[i + 1][0]["scene"] == c[0]["scene"]
        end = nxt if same_scene and nxt - c[-1]["end"] < 0.7 else c[-1]["end"] + 0.35
        out.append({"start": c[0]["start"], "end": end, "words": c})
    return out


def draw_captions(layer, chunks, t):
    active = next((c for c in chunks if c["start"] <= t < c["end"]), None)
    if not active:
        return
    d = ImageDraw.Draw(layer)
    f = font(68, "bold")
    tokens = [(w["text"].upper() + (w.get("punct", "") if w.get("punct") in ("?", "!") else ""), w)
              for w in active["words"]]
    space = d.textlength(" ", font=f)
    widths = [d.textlength(tok, font=f) for tok, _ in tokens]
    # wrap into lines of max 940 px
    lines, line, lw = [], [], 0
    for (tok, w), wd in zip(tokens, widths):
        if line and lw + space + wd > 940:
            lines.append((line, lw))
            line, lw = [], 0
        lw = lw + (space if line else 0) + wd
        line.append((tok, w, wd))
    if line:
        lines.append((line, lw))
    pop = prog(t, active["start"], 0.12)
    lh = 84
    cy = 1345
    y0 = cy - len(lines) * lh / 2
    box_w = max(l[1] for l in lines) + 60
    d.rounded_rectangle([W / 2 - box_w / 2, y0 - 18, W / 2 + box_w / 2, y0 + len(lines) * lh + 10],
                        radius=14, fill=(6, 10, 16, int(200 * pop)))
    d.rectangle([W / 2 - box_w / 2, y0 - 18, W / 2 - box_w / 2 + 8, y0 + len(lines) * lh + 10],
                fill=rgba(AMBER, pop))
    for li, (ln, lwid) in enumerate(lines):
        x = W / 2 - lwid / 2
        y = y0 + li * lh + (1 - pop) * 14
        for tok, w, wd in ln:
            on = w["start"] <= t < w["end"] + 0.05
            past = t >= w["end"]
            col = AMBER if on else (WHITE if past or t >= w["start"] else (200, 208, 216))
            d.text((x, y), tok, font=f, fill=rgba(col, pop), stroke_width=5, stroke_fill=(0, 0, 0, int(255 * pop)))
            x += wd + space


# --------------------------------------------------------------------------- HUD
class HUD:
    def __init__(self, L, duration):
        self.L = L
        self.duration = duration
        start = dt.date(2026, 2, 28)
        self.war_day = (dt.date(2026, 11, 2) - start).days + 1
        self.ticker = self._ticker_strip()
        self.static = self._static()

    def _ticker_strip(self):
        f = font(34, "bold")
        sep = "   ◆   "
        txt = sep.join(self.L["ticker"]) + sep
        tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
        tw = int(tmp.textlength(txt, font=f)) + 1
        strip = Image.new("RGBA", (tw * 2, 60), (0, 0, 0, 0))
        d = ImageDraw.Draw(strip)
        for k in range(2):
            d.text((k * tw, 30), txt, font=f, fill=WHITE, anchor="lm")
        self.tick_w = tw
        return strip

    def _static(self):
        L = self.L
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # header band
        d.rectangle([0, 60, W, 240], fill=(8, 12, 18, 225))
        d.rectangle([0, 238, W, 242], fill=AMBER)
        text_box(d, (52, 112), L["brand"], font(50, "bold"), WHITE, RED, pad=(18, 12), anchor="lm")
        d.text((W - 48, 112), L["date"], font=font(26, "mono"), fill=MUTED, anchor="rm")
        d.text((48, 192), "• " + L["desk"], font=font(36, "bold"), fill=AMBER, anchor="lm")
        # title bar background
        d.rectangle([40, 256, 1040, 326], fill=(10, 16, 24, 235))
        d.rectangle([40, 256, 50, 326], fill=AMBER)
        # ticker band
        d.rectangle([0, 1462, W, 1522], fill=(8, 12, 18, 235))
        d.rectangle([0, 1462, W, 1465], fill=RED)
        return img

    def draw(self, layer, t, scene_idx, scene_t, title):
        L = self.L
        layer.alpha_composite(self.static)
        d = ImageDraw.Draw(layer)
        # LIVE indicator (blinks 1 Hz)
        bx = 52 + d.textlength(L["brand"], font=font(50, "bold")) + 70
        on = (t % 1.0) < 0.6
        d.ellipse([bx - 13, 99, bx + 13, 125], fill=RED if on else (90, 20, 24))
        d.text((bx + 26, 112), L["live"], font=font(30, "bold"), fill=WHITE, anchor="lm")
        # scene title + index
        d.text((72, 291), title, font=font(38, "bold"), fill=WHITE, anchor="lm")
        d.text((1020, 291), f"{scene_idx + 1:02d}/04", font=font(30, "mono"), fill=AMBER, anchor="rm")
        # telemetry line
        d.text((44, 348), L["day_of_war"].format(n=self.war_day), font=font(24, "mono"), fill=MUTED, anchor="lm")
        mm, ss = divmod(int(t), 60)
        d.text((1036, 348), f"T+{mm:02d}:{ss:02d}.{int((t % 1) * 30):02d}", font=font(24, "mono"),
               fill=AMBER, anchor="rm")
        # progress bar
        d.rectangle([40, 362, 1040, 365], fill=(40, 52, 66, 255))
        d.rectangle([40, 362, 40 + 1000 * clamp(t / self.duration), 365], fill=AMBER)
        # ticker
        off = int((t * 150) % self.tick_w)
        crop = self.ticker.crop((off, 0, off + W - 230, 60))
        layer.alpha_composite(crop, (230, 1462))
        text_box(d, (24, 1494), "BREAKING" if L["live"] == "LIVE" else "URGENTE", font(30, "bold"),
                 WHITE, RED, pad=(16, 14), anchor="lm")


# --------------------------------------------------------------------------- scenes
class Scenes:
    def __init__(self, L, lang):
        self.L = L
        self.lang = lang
        px, py, pw, ph = PANEL
        self.box = (px, py, px + pw, py + ph)
        self.layers = [self._s1_static(), self._s2_static(), self._s3_static(), self._s4_static()]

    def _panel_frame(self, d):
        x0, y0, x1, y1 = self.box
        d.rectangle(self.box, outline=rgba(GRID, 1), width=2)
        brackets(d, (x0 - 6, y0 - 6, x1 + 6, y1 + 6), AMBER)

    # ---- Scene 1: Strait of Hormuz
    def _s1_static(self):
        L = self.L
        self.m1 = GeoMap((50.2, 59.6, 23.2, 30.9), (PANEL[2], PANEL[3]))
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        img.alpha_composite(self.m1.image, (PANEL[0], PANEL[1]))
        d = ImageDraw.Draw(img)
        P = self.p1
        C = L["countries"]
        for key, ll, size, col in (("IRAN", (54.0, 29.3), 54, WHITE), ("UAE", (54.0, 23.7), 38, WHITE),
                                   ("OMAN", (58.3, 23.55), 38, WHITE), ("QATAR", (51.25, 25.15), 26, WHITE),
                                   ("GULF", (53.2, 25.25), 30, STEEL), ("OMANGULF", (58.6, 24.55), 28, STEEL)):
            d.text(P(*ll), C[key], font=font(size, "bold"), fill=rgba(col, 0.8 if col == WHITE else 0.7),
                   anchor="mm")
        for name, ll in (("BANDAR ABBAS", (56.27, 27.18)), ("QESHM", (55.8, 26.83)), ("MUSANDAM", (56.25, 26.15))):
            x, y = P(*ll)
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=WHITE)
            d.text((x + 12, y - 16), name, font=font(22, "bold"), fill=rgba(WHITE, 0.85), anchor="ls")
        d.text((PANEL[0] + 18, PANEL[1] + PANEL[3] - 16), L["s1_src"], font=font(20, "mono"),
               fill=rgba(MUTED, 1), anchor="ls")
        self._panel_frame(d)
        return img

    def p1(self, lon, lat):
        x, y = self.m1.px(lon, lat)
        return (PANEL[0] + x, PANEL[1] + y)

    LANE = [(50.4, 27.15), (52.5, 26.35), (54.5, 26.05), (55.8, 26.3), (56.45, 26.52), (56.8, 26.4),
            (57.2, 25.85), (58.3, 24.95), (59.6, 24.4)]
    UNAUTH = [(54.6, 26.3), (55.4, 26.48), (56.1, 26.62), (56.55, 26.74), (57.0, 26.55), (57.35, 26.0)]
    TANKERS = [((56.1, 26.62), 3.4), ((56.82, 26.66), 5.0)]

    def s1(self, layer, t):
        L = self.L
        d = ImageDraw.Draw(layer)
        P = self.p1
        # radar sweep centred on the strait
        cx, cy = P(56.45, 26.5)
        R = 360
        for r in (120, 240, 360):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=rgba(AMBER, 0.22), width=2)
        ang = (t * 70) % 360
        for k in range(26):
            a = math.radians(ang - k * 1.6)
            d.line([(cx, cy), (cx + R * math.cos(a), cy + R * math.sin(a))],
                   fill=rgba(AMBER, 0.16 * (1 - k / 26)), width=5)
        d.line([(cx - R, cy), (cx + R, cy)], fill=rgba(AMBER, 0.15), width=1)
        d.line([(cx, cy - R), (cx, cy + R)], fill=rgba(AMBER, 0.15), width=1)
        # strait label
        a = prog(t, 0.6, 0.8)
        lx, ly = cx + 10, cy - 250
        d.line([(cx, cy - 20), (lx, ly + 22)], fill=rgba(AMBER, a), width=2)
        text_box(d, (lx, ly), L["countries"]["STRAIT"], font(28, "bold"), rgba(SLATE, a), rgba(AMBER, a),
                 pad=(12, 8), anchor="mm")
        # shipping lane (white dashed, drawn on) + moving traffic
        lane = [P(*p) for p in self.LANE]
        part = partial_polyline(lane, prog(t, 0.5, 2.5))
        if len(part) > 1:
            dashed(d, part, rgba(WHITE, 0.75), width=4, offset=t * 40)
        if t > 2.5:
            for k in range(5):
                q = partial_polyline(lane, ((t * 0.035 + k / 5) % 1))[-1]
                d.ellipse([q[0] - 7, q[1] - 7, q[0] + 7, q[1] + 7], fill=rgba(STEEL, 0.9))
            lx, ly = P(52.0, 26.1)
            d.text((lx, ly), L["s1_lane"], font=font(22, "bold"), fill=rgba(WHITE, 0.8), anchor="mm")
        # unauthorized route (red dashed)
        un = [P(*p) for p in self.UNAUTH]
        part = partial_polyline(un, prog(t, 1.5, 2.0))
        if len(part) > 1:
            dashed(d, part, rgba(RED, 0.95), width=5, dash=14, gap=10, offset=t * 30)
        if t > 2.6:
            a = prog(t, 2.6, 0.5)
            ux, uy = P(54.3, 27.2)
            text_box(d, (ux, uy - 8), L["s1_unauth"], font(22, "bold"), rgba(WHITE, a), rgba(RED, a * 0.85),
                     pad=(8, 5), anchor="mb")
        # tanker mine explosions
        for n, ((lon, lat), te) in enumerate(self.TANKERS, 1):
            if t < te:
                continue
            x, y = P(lon, lat)
            dtt = t - te
            if dtt < 1.4:  # blast: flash + expanding rings
                fl = 1 - dtt / 1.4
                for k, rr in enumerate((30, 60, 100)):
                    r = rr * (0.4 + 1.6 * ease(dtt / 1.0))
                    d.ellipse([x - r, y - r, x + r, y + r], outline=rgba((255, 120 + 40 * k, 40), fl), width=6 - k)
                r = 40 * fl + 10
                d.ellipse([x - r, y - r, x + r, y + r], fill=rgba((255, 230, 160), fl))
            pulse = 0.5 + 0.5 * math.sin((t - te) * 6)
            for r, a in ((26 + 10 * pulse, 0.25), (16, 0.6)):
                d.ellipse([x - r, y - r, x + r, y + r], fill=rgba(RED, a))
            d.line([(x - 12, y - 12), (x + 12, y + 12)], fill=WHITE, width=4)
            d.line([(x - 12, y + 12), (x + 12, y - 12)], fill=WHITE, width=4)
            a = prog(t, te + 0.3, 0.4)
            if n == 1:
                (tx, ty), anchor, tip = (x + 20, y - 130), "rm", (x + 10, y - 115)
            else:
                (tx, ty), anchor, tip = (x, y + 66), "mt", (x, y + 58)
            d.line([(x, y + (-18 if n == 1 else 18)), tip], fill=rgba(WHITE, a), width=2)
            text_box(d, (tx, ty), L["s1_tanker"].format(n=n) + " • " + L["s1_mine"],
                     font(22, "bold"), rgba(WHITE, a), rgba(RED, a), pad=(10, 6), anchor=anchor)
        # "2 tankers exploded" badge
        if t > 5.6:
            a = prog(t, 5.6, 0.5)
            x0, y0 = PANEL[0] + 24, PANEL[1] + 24
            d.rectangle([x0, y0, x0 + 520, y0 + 96], fill=(8, 12, 18, int(230 * a)), outline=rgba(RED, a), width=3)
            d.rectangle([x0, y0, x0 + 12, y0 + 96], fill=rgba(RED, a))
            d.text((x0 + 32, y0 + 30), L["s1_tankers_hit"], font=font(32, "bold"), fill=rgba(WHITE, a), anchor="lm")
            d.text((x0 + 32, y0 + 70), L["s1_badge_sub"], font=font(22, "mono"), fill=rgba(MUTED, a),
                   anchor="lm")
        # Brent crude price box
        if t > 7.0:
            a = prog(t, 7.0, 0.5)
            val = 116.72 * (0.7 + 0.3 * prog(t, 7.0, 2.2))
            if t > 9.2:
                val = 116.72
            x1, y1 = PANEL[0] + PANEL[2] - 24, PANEL[1] + PANEL[3] - 50
            x0, y0 = x1 - (560 if self.lang == "en" else 640), y1 - 200
            d.rectangle([x0, y0, x1, y1], fill=(8, 12, 18, int(235 * a)), outline=rgba(AMBER, a), width=3)
            d.text((x0 + 26, y0 + 36), self.L["s1_brent"], font=font(30, "bold"), fill=rgba(AMBER, a), anchor="lm")
            price = f"${val:,.2f}" if self.lang == "en" else f"US$ {val:.2f}".replace(".", ",")
            pf = font(88 if self.lang == "en" else 70, "bold")
            d.text((x0 + 26, y0 + 120), price, font=pf, fill=rgba(WHITE, a), anchor="lm")
            pw = d.textlength(price, font=pf)
            d.text((x0 + 36 + pw, y0 + 138), self.L["s1_bbl"], font=font(30, "bold"), fill=rgba(MUTED, a), anchor="lm")
            tri_x = x1 - 50
            blink = 1.0 if (t * 2) % 1 < 0.7 else 0.4
            d.polygon([(tri_x, y0 + 18), (tri_x - 26, y0 + 58), (tri_x + 26, y0 + 58)], fill=rgba(RED, a * blink))

    # ---- Scene 2: Pickaxe Mountain cross-section
    CS_W, CS_H = 1000, 560
    CS_YLIM = (-150.0, 950.0)

    def surface(self, x):
        return (90 + 640 * np.exp(-((x - 5.0) / 2.4) ** 2) + 230 * np.exp(-((x - 1.2) / 0.8) ** 2)
                + 260 * np.exp(-((x - 8.9) / 0.9) ** 2) + 45 * np.sin(3.1 * x) + 25 * np.sin(7.7 * x + 1.0))

    def cs(self, x, y):
        y0, y1 = self.CS_YLIM
        return (PANEL[0] + x / 10 * self.CS_W, PANEL[1] + (y1 - y) / (y1 - y0) * self.CS_H)

    def _s2_static(self):
        L = self.L
        x = np.linspace(0, 10, 800)
        s = self.surface(x)
        fig = plt.figure(figsize=(self.CS_W / 100, self.CS_H / 100), dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_xlim(0, 10)
        ax.set_ylim(*self.CS_YLIM)
        ax.axis("off")
        c = lambda col, a=1.0: (col[0] / 255, col[1] / 255, col[2] / 255, a)  # noqa: E731
        ax.add_patch(plt.Rectangle((0, self.CS_YLIM[0]), 10, 1100, color=c((10, 16, 24), 0.85), zorder=0))
        for yy in np.arange(-100, 950, 100):
            ax.axhline(yy, color=c(GRID, 0.35), lw=0.8, ls=(0, (3, 5)), zorder=1)
        strata = [((58, 50, 42), 0, 70), ((48, 44, 40), 70, 190), ((38, 38, 40), 190, 360), ((30, 32, 36), 360, 2000)]
        for col, a, b in strata:
            ax.fill_between(x, s - a, np.maximum(s - b, self.CS_YLIM[0]), color=c(col), lw=0, zorder=2)
        for k in range(1, 4):  # strata seams
            ax.plot(x, s - [70, 190, 360][k - 1], color=c((90, 80, 66), 0.35), lw=1, zorder=3)
        ax.plot(x, s, color=c(WHITE, 0.9), lw=2.2, zorder=4)
        ax.fill_between(x, s, s + 14, color=c(AMBER, 0.10), lw=0, zorder=4)
        fig.canvas.draw()
        img_cs = Image.fromarray(np.asarray(fig.canvas.buffer_rgba()).copy(), "RGBA")
        plt.close(fig)

        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle(self.box, fill=(10, 16, 24, 215))
        img.alpha_composite(img_cs, (PANEL[0], PANEL[1]))
        d.text((PANEL[0] + 20, PANEL[1] + 24), L["s2_schem"], font=font(20, "mono"),
               fill=rgba(MUTED, 1), anchor="lm")
        sx, sy = self.cs(1.2, float(self.surface(np.array(1.2))))
        d.text((sx, sy - 22), L["s2_surface"], font=font(22, "bold"), fill=rgba(WHITE, 0.8), anchor="mb")
        # divider under the cross-section
        d.line([(PANEL[0], PANEL[1] + self.CS_H), (PANEL[0] + PANEL[2], PANEL[1] + self.CS_H)], fill=AMBER, width=2)
        self._panel_frame(d)
        return img

    def s2(self, layer, t):
        L = self.L
        d = ImageDraw.Draw(layer)
        top = float(self.surface(np.array(5.0)))
        lvl = 300.0  # tunnel level (schematic units)
        # scan line descending from summit to tunnel level
        sp = prog(t, 0.4, 3.2)
        scan_y = top - (top - lvl) * sp
        x0p, _ = self.cs(0, 0)
        x1p, _ = self.cs(10, 0)
        _, yp = self.cs(0, scan_y)
        if t < 4.2:
            for k in range(10):
                d.line([(x0p, yp - k * 4), (x1p, yp - k * 4)], fill=rgba(AMBER, 0.35 * (1 - k / 10)), width=2)
        # tunnel complex (drawn on progressively)
        tp = prog(t, 2.6, 2.4)
        halls = [(3.75, 280, 4.85, 335), (5.15, 270, 6.25, 330), (4.3, 245, 5.7, 270)]
        corridor = [(2.55, float(self.surface(np.array(2.55)))), (3.0, 330), (3.75, 305), (6.25, 300), (7.0, 330),
                    (7.6, float(self.surface(np.array(7.6))))]
        cor = [self.cs(*p) for p in corridor]
        part = partial_polyline(cor, tp)
        if len(part) > 1:
            d.line(part, fill=rgba(AMBER, 0.95), width=9, joint="curve")
            d.line(part, fill=rgba((255, 230, 170), 0.9), width=3, joint="curve")
        for i, (a, b, c_, e) in enumerate(halls):
            ha = clamp((tp - 0.3 - i * 0.15) / 0.3)
            if ha <= 0:
                continue
            p0, p1 = self.cs(a, e), self.cs(c_, b)
            d.rectangle([p0[0], p0[1], p1[0], p1[1]], fill=rgba(AMBER, 0.35 * ha), outline=rgba(AMBER, ha), width=3)
            for k in range(1, 4):  # internal bays
                xx = p0[0] + (p1[0] - p0[0]) * k / 4
                d.line([(xx, p0[1] + 4), (xx, p1[1] - 4)], fill=rgba(AMBER, 0.5 * ha), width=2)
        if tp > 0.6:
            a = prog(t, 4.0, 0.5)
            hx, hy = self.cs(5.0, 230)
            d.text((hx, hy + 24), L["s2_tunnels"], font=font(26, "bold"), fill=rgba(WHITE, a), anchor="mt")
        # depth ruler (summit -> tunnel level)
        if t > 0.8:
            a = prog(t, 0.8, 0.4)
            rx = self.cs(5.0, 0)[0]
            yt = self.cs(0, top)[1]
            yb = self.cs(0, scan_y if t < 3.6 else lvl + 40)[1]
            d.line([(rx, yt), (rx, yb)], fill=rgba(WHITE, a), width=3)
            for k in range(0, int(yb - yt), 18):
                d.line([(rx - 8, yt + k), (rx + 8, yt + k)], fill=rgba(WHITE, a * 0.7), width=2)
            d.line([(rx - 16, yt), (rx + 16, yt)], fill=rgba(WHITE, a), width=4)
            d.line([(rx - 16, yb), (rx + 16, yb)], fill=rgba(AMBER, a), width=4)
            depth_m = int(100 * prog(t, 0.6, 3.0))
            label = L["s2_depth_val"] if t > 3.6 else f"{depth_m} M"
            bx = rx + 34
            by = (yt + yb) / 2 + 30
            text_box(d, (bx, by), L["s2_depth"], font(22, "bold"), rgba(SLATE, a), rgba(AMBER, a), pad=(8, 4),
                     anchor="ls")
            text_box(d, (bx, by + 14), label, font(34, "bold"), rgba(WHITE, a), (8, 12, 18, int(230 * a)),
                     pad=(10, 6), anchor="lt")
        # target reticle + name
        if t > 4.6:
            a = prog(t, 4.6, 0.5)
            cx, cy = self.cs(5.0, 290)
            r = 92 + 8 * math.sin(t * 5)
            d.ellipse([cx - r, cy - r * 0.62, cx + r, cy + r * 0.62], outline=rgba(RED, a), width=3)
            for ang in (0, 90, 180, 270):
                ra = math.radians(ang)
                d.line([(cx + math.cos(ra) * (r - 14), cy + math.sin(ra) * (r - 14) * 0.62),
                        (cx + math.cos(ra) * (r + 18), cy + math.sin(ra) * (r + 18) * 0.62)], fill=rgba(RED, a), width=4)
            nx, ny = PANEL[0] + PANEL[2] - 20, PANEL[1] + 60
            text_box(d, (nx, ny), L["s2_target"], font(20, "bold"), rgba(WHITE, a), rgba(RED, a), pad=(8, 4), anchor="rm")
            d.text((nx, ny + 40), "PICKAXE MOUNTAIN", font=font(34, "bold"), fill=rgba(WHITE, a), anchor="rm")
            d.text((nx, ny + 76), L["s2_name"], font=font(26, "bold"), fill=rgba(AMBER, a), anchor="rm")
            d.text((nx, ny + 106), L["s2_loc"], font=font(20, "mono"), fill=rgba(MUTED, a), anchor="rm")
        # lower metrics: war cost + quote
        y0 = PANEL[1] + self.CS_H + 22
        a = prog(t, 5.8, 0.5)
        if a > 0:
            x0 = PANEL[0] + 22
            d.rectangle([x0, y0, x0 + 460, y0 + 254], fill=(8, 12, 18, int(235 * a)), outline=rgba(AMBER, a), width=3)
            d.text((x0 + 24, y0 + 34), L["s2_cost"], font=font(26, "bold"), fill=rgba(AMBER, a), anchor="lm")
            v = 47.1 * prog(t, 5.8, 2.2)
            s = f"${v:.1f}B" if self.lang == "en" else f"US$ {v:.1f} BI".replace(".", ",")
            d.text((x0 + 24, y0 + 128), s, font=font(92 if self.lang == "en" else 60, "bold"), fill=rgba(WHITE, a),
                   anchor="lm")
            d.text((x0 + 24, y0 + 214), L["s2_cost_sub"], font=font(22, "mono"), fill=rgba(MUTED, a), anchor="lm")
        a = prog(t, 1.6, 0.6)
        if a > 0:
            x0 = PANEL[0] + 504
            d.rectangle([x0, y0, x0 + 474, y0 + 254], fill=(8, 12, 18, int(235 * a)), outline=rgba(GRID, a), width=2)
            d.rectangle([x0, y0, x0 + 10, y0 + 254], fill=rgba(WHITE, a))
            d.text((x0 + 34, y0 + 14), "“", font=font(64, "bold"), fill=rgba(AMBER, a), anchor="lt")
            d.multiline_text((x0 + 34, y0 + 76), L["s2_quote"], font=font(29, "bold"),
                             fill=rgba(WHITE, a), spacing=9)

    # ---- Scene 3: Two-Day Plan + Saudi alert
    def _s3_static(self):
        L = self.L
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x0, y0, x1, y1 = self.box
        d.rectangle(self.box, fill=(10, 16, 24, 200))
        self.m3 = GeoMap((48.6, 51.6, 24.9, 27.3), (420, 300), grid_step=0.5)
        self.m3_pos = (x1 - 22 - 420, y0 + 548)
        img.alpha_composite(self.m3.image, self.m3_pos)
        d.rectangle([self.m3_pos[0], self.m3_pos[1], self.m3_pos[0] + 420, self.m3_pos[1] + 300], outline=GRID, width=2)
        self._panel_frame(d)
        return img

    def p3(self, lon, lat):
        x, y = self.m3.px(lon, lat)
        return (self.m3_pos[0] + x, self.m3_pos[1] + y)

    def _ship(self, d, cx, cy, s, col):
        d.polygon([(cx - 70 * s, cy), (cx + 80 * s, cy), (cx + 56 * s, cy + 30 * s), (cx - 60 * s, cy + 30 * s)], fill=col)
        d.rectangle([cx - 46 * s, cy - 26 * s, cx - 6 * s, cy], fill=col)
        d.rectangle([cx - 36 * s, cy - 50 * s, cx - 20 * s, cy - 26 * s], fill=col)
        for k in range(3):
            yy = cy + 44 * s + k * 14 * s
            pts = [(cx - 90 * s + i * 12 * s, yy + 5 * s * math.sin(i * 1.3 + k)) for i in range(16)]
            d.line(pts, fill=col, width=3)

    def _doc(self, d, cx, cy, s, col, check_p):
        d.rectangle([cx - 52 * s, cy - 66 * s, cx + 52 * s, cy + 66 * s], outline=col, width=5)
        for k in range(4):
            d.line([(cx - 34 * s, cy - 36 * s + k * 22 * s), (cx + 34 * s, cy - 36 * s + k * 22 * s)], fill=col, width=4)
        if check_p > 0:
            pts = partial_polyline([(cx + 10 * s, cy + 50 * s), (cx + 34 * s, cy + 76 * s), (cx + 84 * s, cy + 14 * s)],
                                   check_p)
            if len(pts) > 1:
                d.line(pts, fill=AMBER, width=10, joint="curve")

    def s3(self, layer, t):
        L = self.L
        d = ImageDraw.Draw(layer)
        x0, y0, x1, y1 = self.box
        a = prog(t, 0.0, 0.5)
        d.text((x0 + 24, y0 + 40), L["s3_by"], font=font(22, "bold"), fill=rgba(WHITE, a), anchor="lm")
        d.text((x0 + 24, y0 + 78), L["s3_doha"], font=font(22, "mono"), fill=rgba(MUTED, a), anchor="lm")
        if t > 1.0:
            sa = prog(t, 1.0, 0.3)
            text_box(d, (x1 - 24, y0 + 58), L["s3_status"], font(26, "bold"), rgba(AMBER, sa), (8, 12, 18, int(230 * sa)),
                     pad=(12, 8), anchor="rm")
            l, tt, r, b = d.textbbox((x1 - 24, y0 + 58), L["s3_status"], font=font(26, "bold"), anchor="rm")
            d.rectangle([l - 12, tt - 8, r + 12, b + 8], outline=rgba(AMBER, sa), width=3)
        # Day cards (split screen)
        cards = [(x0 + 22, L["s3_day1"], L["s3_day1_txt"], L["s3_day1_sub"], WHITE, 0.5),
                 (x0 + 518, L["s3_day2"], L["s3_day2_txt"], L["s3_day2_sub"], AMBER, 3.0)]
        cy0, cy1 = y0 + 120, y0 + 470
        for i, (cx, day, txt, sub, col, ts) in enumerate(cards):
            p = prog(t, ts, 0.6)
            if p <= 0:
                continue
            off = (1 - p) * (-80 if i == 0 else 80)
            bx0, bx1 = cx + off, cx + 460 + off
            d.rectangle([bx0, cy0, bx1, cy1], fill=(14, 22, 32, int(240 * p)), outline=rgba(col, p), width=3)
            d.rectangle([bx0, cy0, bx1, cy0 + 70], fill=rgba(col, p))
            d.text((bx0 + 24, cy0 + 35), day, font=font(42, "bold"), fill=rgba(SLATE, p), anchor="lm")
            d.text((bx1 - 20, cy0 + 35), sub, font=font(18, "bold"), fill=rgba(SLATE, p), anchor="rm")
            d.multiline_text((bx0 + 24, cy0 + 96), txt, font=font(46, "bold"), fill=rgba(WHITE, p), spacing=8)
            if i == 0:
                self._doc(d, bx1 - 110, cy0 + 262, 0.8, rgba(WHITE, p * 0.9), prog(t, 1.6, 0.7))
            else:
                bob = 4 * math.sin(t * 2.4)
                self._ship(d, bx1 - 150, cy0 + 268 + bob, 0.95, rgba(AMBER, p))
        # arrow between days
        if t > 2.2:
            p = prog(t, 2.2, 0.6)
            ax_, ay = x0 + 500, (cy0 + cy1) / 2
            d.ellipse([ax_ - 40, ay - 40, ax_ + 40, ay + 40], fill=rgba(AMBER, p), outline=rgba(SLATE, p), width=4)
            d.polygon([(ax_ - 14, ay - 20), (ax_ + 20, ay), (ax_ - 14, ay + 20)], fill=rgba(SLATE, p))
        # timeline
        ty = y0 + 505
        d.rectangle([x0 + 22, ty, x1 - 22, ty + 10], fill=(40, 52, 66, 255))
        d.rectangle([x0 + 22, ty, x0 + 22 + (x1 - x0 - 44) * prog(t, 0.5, 4.0), ty + 10], fill=AMBER)
        for frac, lab in ((0.0, "D1"), (0.5, "D2"), (1.0, "")):
            xx = x0 + 22 + (x1 - x0 - 44) * frac
            d.ellipse([xx - 10, ty - 5, xx + 10, ty + 15], fill=WHITE)
            if lab:
                d.text((xx + 16, ty + 30), lab, font=font(20, "mono"), fill=MUTED, anchor="lm")
        # Saudi regional alert
        if t > 6.0:
            p = prog(t, 6.0, 0.5)
            ax0, ay0 = x0 + 22, y0 + 548
            flash = 0.55 + 0.45 * (1 if (t * 2.5) % 1 < 0.5 else 0)
            d.rectangle([ax0, ay0, ax0 + 524, ay0 + 300], fill=(30, 8, 10, int(220 * p)), outline=rgba(RED, p), width=4)
            d.rectangle([ax0, ay0, ax0 + 524, ay0 + 58], fill=rgba(RED, p * flash))
            d.text((ax0 + 18, ay0 + 29), "⚠ " + L["s3_alert"], font=font(25 if self.lang == "en" else 21, "bold"), fill=rgba(WHITE, p), anchor="lm")
            d.multiline_text((ax0 + 18, ay0 + 82), L["s3_alert_txt"], font=font(25, "bold"), fill=rgba(WHITE, p),
                             spacing=10)
            d.text((ax0 + 18, ay0 + 196), L["s3_claimed"], font=font(20, "mono"), fill=rgba(MUTED, p), anchor="lm")
            d.text((ax0 + 18, ay0 + 236), f"{L['s3_rt']}  •  {L['s3_ab']}", font=font(32, "bold"), fill=rgba(AMBER, p),
                   anchor="lm")
            d.text((ax0 + 18, ay0 + 276), L["s3_source"], font=font(18, "mono"),
                   fill=rgba(MUTED, p), anchor="lm")
            # inset markers
            for name, ll, dx in ((L["s3_rt"], (50.16, 26.64), 1), (L["s3_ab"], (49.68, 25.93), 1)):
                x, y = self.p3(*ll)
                r = 12 + 8 * (0.5 + 0.5 * math.sin(t * 6))
                d.ellipse([x - r, y - r, x + r, y + r], outline=rgba(RED, p), width=3)
                d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=rgba(RED, p))
                d.text((x + 16 * dx, y - 14), name, font=font(20, "bold"), fill=rgba(WHITE, p), anchor="ls")
            # drone tracks from the south-west being intercepted
            for k, (src, dst) in enumerate((((48.7, 25.0), (49.62, 25.99)), ((49.2, 24.95), (50.1, 26.58)))):
                dp = clamp((t - 6.5 - k * 0.6) / 1.6)
                s_ = self.p3(*src)
                e_ = self.p3(*dst)
                stop = 0.8
                q = (s_[0] + (e_[0] - s_[0]) * min(dp, stop), s_[1] + (e_[1] - s_[1]) * min(dp, stop))
                if dp > 0:
                    dashed(d, [s_, q], rgba(WHITE, p * 0.8), width=3, dash=8, gap=6)
                if dp >= stop:
                    br = 8 + 30 * clamp((dp - stop) / 0.2)
                    d.ellipse([q[0] - br, q[1] - br, q[0] + br, q[1] + br], outline=rgba(AMBER, p), width=3)
                    d.line([(q[0] - 10, q[1] - 10), (q[0] + 10, q[1] + 10)], fill=rgba(AMBER, p), width=4)
                    d.line([(q[0] - 10, q[1] + 10), (q[0] + 10, q[1] - 10)], fill=rgba(AMBER, p), width=4)
            mx, my = self.m3_pos
            d.text((mx + 12, my + 288), L["s3_inset"], font=font(16, "mono"), fill=rgba(MUTED, p),
                   anchor="ls")

    # ---- Scene 4: Diplomacy vs escalation outro
    def _s4_static(self):
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle(self.box, fill=(10, 16, 24, 205))
        self._panel_frame(d)
        return img

    def s4(self, layer, t):
        L = self.L
        d = ImageDraw.Draw(layer)
        x0, y0, x1, y1 = self.box
        cols = [(x0 + 22, L["s4_us"], L["s4_us_pts"], WHITE, 0.2), (x0 + 518, L["s4_ir"], L["s4_ir_pts"], AMBER, 0.6)]
        for cx, head, pts, col, ts in cols:
            p = prog(t, ts, 0.5)
            if p <= 0:
                continue
            d.rectangle([cx, y0 + 22, cx + 460, y0 + 540], fill=(14, 22, 32, int(240 * p)), outline=rgba(col, p), width=3)
            d.rectangle([cx, y0 + 22, cx + 460, y0 + 92], fill=rgba(col, p))
            d.text((cx + 22, y0 + 57), head, font=font(36, "bold"), fill=rgba(SLATE, p), anchor="lm")
            yy = y0 + 122
            for k, txt in enumerate(pts):
                bp = prog(t, ts + 0.6 + k * 0.9, 0.4)
                if bp <= 0:
                    break
                d.rectangle([cx + 22, yy + 8, cx + 34, yy + 20], fill=rgba(col, bp))
                d.multiline_text((cx + 50 - (1 - bp) * 20, yy), txt, font=font(26, "bold"), fill=rgba(WHITE, bp),
                                 spacing=8)
                nl = txt.count("\n") + 1
                yy += 36 * nl + 50
        # outlook gauge
        gy = y0 + 640
        p = prog(t, 3.2, 0.6)
        if p > 0:
            gx0, gx1 = x0 + 80, x1 - 80
            d.text(((gx0 + gx1) / 2, gy - 60), "OUTLOOK" if self.lang == "en" else "CENÁRIO", font=font(24, "mono"),
                   fill=rgba(MUTED, p), anchor="mm")
            steps = 40
            for i in range(steps):
                f = i / (steps - 1)
                col = tuple(int(WHITE[j] * (1 - f) + RED[j] * f) for j in range(3))
                xx = gx0 + (gx1 - gx0) * f
                d.rectangle([xx, gy - 12, xx + (gx1 - gx0) / steps - 3, gy + 12], fill=rgba(col, p))
            nx = (gx0 + gx1) / 2 + (gx1 - gx0) * 0.18 * math.sin(t * 1.7) * p
            d.polygon([(nx, gy - 26), (nx - 18, gy - 50), (nx + 18, gy - 50)], fill=rgba(AMBER, p))
            d.line([(nx, gy - 26), (nx, gy + 26)], fill=rgba(AMBER, p), width=5)
            d.text((gx0, gy + 50), L["s4_dip"], font=font(30, "bold"), fill=rgba(WHITE, p), anchor="lm")
            d.text((gx1, gy + 50), L["s4_esc"], font=font(30, "bold"), fill=rgba(RED, p), anchor="rm")
            d.text(((gx0 + gx1) / 2, gy + 110), "UNRESOLVED" if self.lang == "en" else "INDEFINIDO", font=font(26, "bold"),
                   fill=rgba(AMBER, p * (0.6 + 0.4 * math.sin(t * 4))), anchor="mm")
        d.text((x0 + 22, y1 - 24), "ATTRIBUTED OFFICIAL STATEMENTS • NOV 2026" if self.lang == "en"
               else "DECLARAÇÕES OFICIAIS ATRIBUÍDAS • NOV 2026", font=font(18, "mono"), fill=MUTED, anchor="ls")
        # lower-third CTA
        p = prog(t, 5.5, 0.6)
        if p > 0:
            lx = -700 * (1 - p)
            d.rectangle([lx + 0, 1540, lx + 900, 1660], fill=(8, 12, 18, 240))
            d.rectangle([lx + 0, 1540, lx + 900, 1600], fill=RED)
            d.rectangle([lx + 900, 1540, lx + 920, 1660], fill=AMBER)
            d.text((lx + 40, 1570), L["s4_follow"], font=font(40, "bold"), fill=WHITE, anchor="lm")
            d.text((lx + 40, 1630), L["s4_follow_sub"], font=font(30, "bold"), fill=AMBER, anchor="lm")

    def draw(self, layer, idx, scene_t):
        base = self.layers[idx]
        fade = prog(scene_t, 0, 0.35)
        if fade < 1:
            base = base.copy()
            base.putalpha(base.getchannel("A").point(lambda v: int(v * fade)))
        layer.alpha_composite(base)
        getattr(self, f"s{idx + 1}")(layer, scene_t)
        if scene_t < 0.45 and idx > 0:  # transition: amber scan wipe
            d = ImageDraw.Draw(layer)
            y = PANEL[1] + PANEL[3] * (scene_t / 0.45)
            d.rectangle([0, y - 6, W, y + 6], fill=rgba(AMBER, 0.85))
            d.rectangle([0, y - 40, W, y - 6], fill=rgba(AMBER, 0.15))


class Renderer:
    def __init__(self, L, lang, scenes, duration, words, script_text, assets_dir):
        self.L = L
        self.scenes_t = scenes
        self.duration = duration
        print("  building static layers (matplotlib maps + cross-section)...")
        self.bg = Background(assets_dir, len(scenes))
        self.hud = HUD(L, duration)
        self.sc = Scenes(L, lang)
        self.scan = scanlines()
        self.titles = [L["s1_title"], L["s2_title"], L["s3_title"], L["s4_title"]]
        for i, seg in enumerate(script_text):
            attach_punctuation([w for w in words if w["scene"] == i], seg)
        self.chunks = build_caption_chunks(words)

    def scene_at(self, t):
        for i, (a, b) in enumerate(self.scenes_t):
            if a <= t < b:
                return i, t - a
        return len(self.scenes_t) - 1, t - self.scenes_t[-1][0]

    def frame(self, t):
        idx, st = self.scene_at(t)
        img = self.bg.frame(t, idx, st)
        img.alpha_composite(self.scan)
        self.sc.draw(img, idx, st)
        self.hud.draw(img, t, idx, st, self.titles[idx])
        draw_captions(img, self.chunks, t)
        # global fade in/out
        g = min(prog(t, 0, 0.4), 1 - clamp((t - (self.duration - 0.5)) / 0.5))
        out = img.convert("RGB")
        if g < 1:
            out = Image.eval(out, lambda v: int(v * g))
        return out
