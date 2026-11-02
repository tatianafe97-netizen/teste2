"""Frame renderer: European geopolitical broadcast package (Pillow).

Every frame is drawn with Pillow onto either a navy studio background or the
B-roll found in ``assets/`` (tinted + vignetted), then piped to FFmpeg.
"""

from __future__ import annotations

import math
import re
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import basemap
from ffmpeg_utils import ffmpeg_bin
from script_content import DURATION, FPS, HEIGHT, SCENES, TICKER, WIDTH

# ------------------------------------------------------------------ palette
NAVY_DEEP = (5, 13, 34)
NAVY = (10, 27, 64)
NAVY_PANEL = (12, 31, 72)
CRIMSON = (220, 20, 60)
CRIMSON_DARK = (120, 10, 32)
WHITE = (255, 255, 255)
OFFWHITE = (226, 232, 244)
GOLD = (242, 193, 78)
SLATE = (132, 152, 190)
STEEL = (64, 82, 118)
POLICE_BLUE = (40, 110, 255)

CONTENT_TOP, CONTENT_BOTTOM = 282, 1125
CAPTION_CY = 1262
TICKER_Y = 1408

# ------------------------------------------------------------------- fonts
_MPL_TTF = None


def _mpl_font(name):
    global _MPL_TTF
    if _MPL_TTF is None:
        import matplotlib

        _MPL_TTF = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    return str(_MPL_TTF / name)


FONT_CANDIDATES = {
    "bold": ["/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
             "/Library/Fonts/Arial Bold.ttf", ("mpl", "DejaVuSans-Bold.ttf")],
    "regular": ["/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
                "/Library/Fonts/Arial.ttf", ("mpl", "DejaVuSans.ttf")],
    "italic": ["/usr/share/fonts/truetype/liberation/LiberationSans-Italic.ttf",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf", ("mpl", "DejaVuSans-Oblique.ttf")],
    "heavy": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", ("mpl", "DejaVuSans-Bold.ttf")],
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", ("mpl", "DejaVuSansMono-Bold.ttf")],
}


@lru_cache(maxsize=None)
def font(style: str, size: int) -> ImageFont.FreeTypeFont:
    for cand in FONT_CANDIDATES[style]:
        path = _mpl_font(cand[1]) if isinstance(cand, tuple) else cand
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def text_w(text, f):
    return f.getlength(text)


def fit_font(text, style, size, max_w, min_size=16):
    while size > min_size and text_w(text, font(style, size)) > max_w:
        size -= 2
    return font(style, size)


def wrap(text, f, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if text_w(trial, f) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


# ----------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out(x):
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_back(x):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def paste(canvas, img, xy, opacity=1.0):
    if opacity <= 0.003:
        return
    if opacity < 0.997:
        alpha = img.getchannel("A").point(lambda v: int(v * opacity))
        canvas.paste(img, (int(xy[0]), int(xy[1])), alpha)
    else:
        canvas.paste(img, (int(xy[0]), int(xy[1])), img)


def panel(w, h, fill, radius=18, outline=None, width=2):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=fill, outline=outline, width=width)
    return img


def shadowed(img, blur=14, offset=(0, 10), alpha=150):
    pad = blur * 3
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    sh = Image.new("RGBA", img.size, (0, 0, 0, alpha))
    sh.putalpha(img.getchannel("A").point(lambda v: v * alpha // 255))
    out.paste(sh, (pad + offset[0], pad + offset[1]), sh)
    out = out.filter(ImageFilter.GaussianBlur(blur))
    out.alpha_composite(img, (pad, pad))
    return out, pad


def star_points(cx, cy, r_out, r_in, n=5, rot=-90):
    pts = []
    for i in range(n * 2):
        r = r_out if i % 2 == 0 else r_in
        a = math.radians(rot + i * 180 / n)
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def person_icon(size, color, accent):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([0, 0, size - 1, size - 1], fill=(*accent, 255))
    s = size
    d.ellipse([s * 0.33, s * 0.16, s * 0.67, s * 0.50], fill=color)
    d.chord([s * 0.16, s * 0.54, s * 0.84, s * 1.18], 180, 360, fill=color)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
    img.putalpha(Image.fromarray(np.minimum(np.array(img.getchannel("A")), np.array(mask))))
    return img


PLANE = [(0, -1.0), (0.12, -0.7), (0.13, -0.25), (0.95, 0.12), (0.95, 0.27), (0.13, 0.08), (0.1, 0.62),
         (0.38, 0.82), (0.38, 0.95), (0, 0.86), (-0.38, 0.95), (-0.38, 0.82), (-0.1, 0.62), (-0.13, 0.08),
         (-0.95, 0.27), (-0.95, 0.12), (-0.13, -0.25), (-0.12, -0.7)]


def plane_poly(cx, cy, heading_deg, scale):
    th = math.radians(heading_deg)
    c, s = math.cos(th), math.sin(th)
    return [(cx + scale * (x * c - y * s), cy + scale * (x * s + y * c)) for x, y in PLANE]


class Polyline:
    def __init__(self, pts):
        self.pts = pts
        self.cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            self.cum.append(self.cum[-1] + math.dist(a, b))
        self.length = self.cum[-1]

    def upto(self, p):
        """Points up to fraction p, plus the head point and screen heading."""
        target = clamp(p) * self.length
        i = 1
        while i < len(self.cum) - 1 and self.cum[i] < target:
            i += 1
        a, b = self.pts[i - 1], self.pts[i]
        seg = self.cum[i] - self.cum[i - 1] or 1.0
        f = clamp((target - self.cum[i - 1]) / seg)
        head = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
        hdg = math.degrees(math.atan2(b[0] - a[0], -(b[1] - a[1])))
        return self.pts[:i] + [head], head, hdg, i - 1


# ------------------------------------------------------------------ B-roll
ASSET_EXT_VIDEO = {".mp4", ".mov", ".m4v", ".webm"}
ASSET_EXT_IMAGE = {".jpg", ".jpeg", ".png"}


def find_assets(asset_dir: Path):
    if not asset_dir.exists():
        return []
    return sorted(p for p in asset_dir.iterdir()
                  if p.suffix.lower() in ASSET_EXT_VIDEO | ASSET_EXT_IMAGE and not p.name.startswith("."))


class BrollReader:
    """Streams 1080x1920 RGB frames of the concatenated B-roll via FFmpeg."""

    def __init__(self, assets: list[Path]):
        n = len(assets)
        seg = DURATION / n
        cmd = [ffmpeg_bin(), "-v", "error"]
        filters = []
        for i, a in enumerate(assets):
            if a.suffix.lower() in ASSET_EXT_IMAGE:
                cmd += ["-loop", "1", "-framerate", str(FPS), "-t", f"{seg + 0.5:.3f}", "-i", str(a)]
                frames = int((seg + 0.5) * FPS)
                filters.append(
                    f"[{i}:v]scale=1188:2112:force_original_aspect_ratio=increase,crop=1188:2112,"
                    f"zoompan=z='min(1.0+0.0007*on,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                    f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},trim=duration={seg:.3f},setpts=PTS-STARTPTS,"
                    f"setsar=1,format=rgb24[v{i}]")
            else:
                cmd += ["-stream_loop", "-1", "-t", f"{seg + 0.5:.3f}", "-i", str(a)]
                filters.append(
                    f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},"
                    f"fps={FPS},trim=duration={seg:.3f},setpts=PTS-STARTPTS,setsar=1,format=rgb24[v{i}]")
        concat = "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0"
        filters.append(f"{concat},eq=brightness=-0.06:saturation=0.7:contrast=1.05,"
                       f"vignette=angle=PI/3.4,format=rgb24[out]")
        cmd += ["-filter_complex", ";".join(filters), "-map", "[out]", "-t", str(DURATION),
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        self.frame_bytes = WIDTH * HEIGHT * 3
        self.last = None

    def next(self):
        buf = self.proc.stdout.read(self.frame_bytes)
        if len(buf) == self.frame_bytes:
            self.last = np.frombuffer(buf, np.uint8).reshape(HEIGHT, WIDTH, 3)
        return self.last

    def close(self):
        try:
            self.proc.stdout.close()
            self.proc.kill()
        except Exception:
            pass


# ------------------------------------------------------------- renderer
def norm_word(w):
    return re.sub(r"[^\w]", "", w.lower())


class Renderer:
    def __init__(self, words, lang: str, build_dir: Path, cache_dir: Path, asset_dir: Path):
        self.words = words
        self.lang = lang
        self.build_dir = build_dir
        self.assets = find_assets(asset_dir)
        self._bg = self._make_background()
        self._bg_arr = np.asarray(self._bg, dtype=np.uint16)
        self._vignette = self._make_vignette()
        self._header = self._make_header()
        self._ticker = self._make_ticker()
        self._chunks = self._make_chunks()
        self._caption_cache: dict = {}
        self._build_scene1(cache_dir)
        self._build_scene2()
        self._build_scene3()
        self._build_scene4()

    # ---------------------------------------------------------- cue lookup
    def cue(self, seg, candidates, default):
        for w in self.words:
            if w.segment == seg and any(norm_word(w.text).startswith(c) for c in candidates):
                return w.start
        return default

    # ----------------------------------------------------------- background
    def _make_background(self):
        y = np.linspace(0, 1, HEIGHT)[:, None]
        x = np.linspace(0, 1, WIDTH)[None, :]
        top, bot = np.array(NAVY_DEEP), np.array((11, 30, 70))
        grad = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
        # soft crimson glow, upper-right, and gold glow lower-left
        g1 = np.exp(-(((x - 0.95) ** 2) / 0.10 + ((y - 0.18) ** 2) / 0.04))[..., None]
        g2 = np.exp(-(((x - 0.05) ** 2) / 0.12 + ((y - 0.80) ** 2) / 0.05))[..., None]
        img = grad + g1 * np.array([70, 6, 22]) + g2 * np.array([30, 24, 6])
        img = np.broadcast_to(img, (HEIGHT, WIDTH, 3)).copy()
        im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im, "RGBA")
        for gx in range(0, WIDTH, 60):
            d.line([(gx, 0), (gx, HEIGHT)], fill=(80, 120, 200, 14))
        for gy in range(0, HEIGHT, 60):
            d.line([(0, gy), (WIDTH, gy)], fill=(80, 120, 200, 14))
        return im

    def _make_vignette(self):
        y = np.linspace(-1, 1, HEIGHT)[:, None]
        x = np.linspace(-1, 1, WIDTH)[None, :]
        r = np.sqrt((x * 0.9) ** 2 + (y * 0.75) ** 2)
        v = 1.0 - 0.55 * np.clip((r - 0.45) / 0.8, 0, 1) ** 1.6
        return (v[..., None] * 256).astype(np.uint16)

    def base_frame(self, broll_frame):
        if broll_frame is None:
            return self._bg.copy()
        # B-roll sits behind a translucent navy grade + dark vignette
        mixed = (broll_frame.astype(np.uint16) * 92 + self._bg_arr * 164) >> 8
        mixed = (mixed * self._vignette) >> 8
        return Image.fromarray(mixed.astype(np.uint8))

    # --------------------------------------------------------------- header
    def _make_header(self):
        img = Image.new("RGBA", (WIDTH, 270), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, WIDTH, 8], fill=WHITE)
        d.rectangle([0, 8, WIDTH, 16], fill=CRIMSON)
        d.rectangle([0, 16, WIDTH, 198], fill=(*NAVY_DEEP, 238))
        # LIVE badge
        d.rounded_rectangle([40, 36, 168, 92], radius=10, fill=CRIMSON)
        d.text((118, 64), "LIVE", font=font("bold", 30), fill=WHITE, anchor="mm")
        f1 = font("bold", 52)
        d.text((190, 64), "GLOBAL NEWS 1.0", font=f1, fill=WHITE, anchor="lm")
        x2 = 190 + text_w("GLOBAL NEWS 1.0", f1) + 16
        f2 = fit_font("• EUROPE DESK:", "bold", 34, WIDTH - 40 - x2)
        d.text((x2, 66), "• EUROPE DESK:", font=f2, fill=GOLD, anchor="lm")
        f3 = fit_font("WARSAW CONSTITUTIONAL CRISIS", "bold", 54, WIDTH - 80)
        d.text((40, 150), "WARSAW CONSTITUTIONAL CRISIS", font=f3, fill=WHITE, anchor="lm")
        d.rectangle([0, 198, WIDTH, 202], fill=GOLD)
        d.rectangle([0, 202, WIDTH, 208], fill=(*NAVY_DEEP, 220))
        return img

    KICKERS = ["MID-AIR U-TURN", "COURTROOM POWER STRUGGLE", "NAWROCKI vs. TUSK", "RULE-OF-LAW IMPLICATIONS"]

    def draw_header(self, canvas, d, t):
        canvas.paste(self._header, (0, 0), self._header)
        # pulsing live dot
        pulse = 0.5 + 0.5 * math.sin(t * 2 * math.pi * 1.2)
        d.ellipse([52, 57, 66, 71], fill=(255, 255, 255, int(120 + 135 * pulse)))
        # progress bar
        d.rectangle([0, 202, int(WIDTH * t / DURATION), 208], fill=GOLD)
        # kicker bar
        si = next(i for i, (a, b) in enumerate(SCENES) if t < b or i == len(SCENES) - 1)
        lt = t - SCENES[si][0]
        slide = ease_out(prog(lt, 0.0, 0.45))
        d.rectangle([0, 216, 236, 266], fill=CRIMSON)
        d.text((118, 241), "BREAKING", font=font("heavy", 28), fill=WHITE, anchor="mm")
        kick = self.KICKERS[si]
        fk = font("heavy", 28)
        kw = int(text_w(kick, fk) + 48)
        x0 = 236 - kw + int(kw * slide)
        d.rectangle([236, 216, 236 + kw, 266], fill=(*NAVY_DEEP, 200))
        d.rectangle([x0, 216, x0 + kw, 266], fill=WHITE)
        d.text((x0 + 24, 241), kick, font=fk, fill=NAVY_DEEP, anchor="lm")
        # telemetry clock on the right
        d.text((WIDTH - 40, 241), "WARSAW 30.10.2026", font=font("mono", 22), fill=SLATE, anchor="rm")

    # --------------------------------------------------------------- ticker
    def _make_ticker(self):
        f = font("bold", 30)
        text = TICKER * 2
        w = int(text_w(text, f)) + 20
        img = Image.new("RGBA", (w, 58), (*NAVY_DEEP, 235))
        d = ImageDraw.Draw(img)
        d.text((0, 29), text, font=f, fill=OFFWHITE, anchor="lm")
        self._ticker_period = text_w(TICKER, f)
        return img

    def draw_ticker(self, canvas, d, t):
        y = TICKER_Y
        off = int((t * 130) % self._ticker_period)
        strip = self._ticker.crop((off, 0, off + WIDTH - 250, 58))
        canvas.paste(strip, (250, y), strip)
        d.rectangle([0, y, 250, y + 58], fill=CRIMSON)
        d.text((125, y + 29), "EUROPE DESK", font=font("heavy", 24), fill=WHITE, anchor="mm")
        d.rectangle([0, y + 58, WIDTH, y + 62], fill=GOLD)
        d.text((40, y + 92), "SOURCES: REUTERS • EURONEWS • 30 OCT 2026", font=font("mono", 20), fill=SLATE,
               anchor="lm")

    # ------------------------------------------------------------- captions
    def _make_chunks(self):
        chunks, cur = [], []
        for i, w in enumerate(self.words):
            gap = cur and (w.start - self.words[i - 1].end > 0.7 or w.segment != self.words[i - 1].segment)
            if cur and (gap or len(cur) >= 4 or sum(len(self.words[j].text) + 1 for j in cur) + len(w.text) > 24):
                chunks.append(cur)
                cur = []
            cur.append(i)
            if re.search(r"[.,:;!?]$", w.text) and len(cur) >= 2:
                chunks.append(cur)
                cur = []
        if cur:
            chunks.append(cur)
        out = []
        for k, idx in enumerate(chunks):
            start = self.words[idx[0]].start
            end = self.words[idx[-1]].end + 0.25
            if k + 1 < len(chunks):
                end = min(max(end, self.words[idx[-1]].end + 0.05), self.words[chunks[k + 1][0]].start)
            out.append((start, end, idx))
        return out

    def _caption_img(self, ci, active):
        key = (ci, active)
        if key in self._caption_cache:
            return self._caption_cache[key]
        _, _, idx = self._chunks[ci]
        f = font("heavy", 64)
        toks = [self.words[i].text.upper() for i in idx]
        max_w = 860
        lines, cur, cur_w = [], [], 0.0
        space = text_w(" ", f)
        for j, tok in enumerate(toks):
            tw = text_w(tok, f)
            if cur and cur_w + space + tw > max_w:
                lines.append(cur)
                cur, cur_w = [], 0.0
            cur_w += (space if cur else 0) + tw
            cur.append((j, tok, tw))
        lines.append(cur)
        lh = 82
        box_w = int(max(sum(tw for _, _, tw in ln) + space * (len(ln) - 1) for ln in lines)) + 64
        box_h = lh * len(lines) + 34
        img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, box_w - 1, box_h - 1], radius=16, fill=(*NAVY_DEEP, 205))
        d.rectangle([0, 12, 7, box_h - 12], fill=CRIMSON)
        for li, ln in enumerate(lines):
            lw = sum(tw for _, _, tw in ln) + space * (len(ln) - 1)
            x = (box_w - lw) / 2
            y = 17 + li * lh + lh / 2
            for j, tok, tw in ln:
                col = GOLD if j == active else WHITE
                d.text((x, y), tok, font=f, fill=col, anchor="lm", stroke_width=5, stroke_fill=(0, 0, 0))
                x += tw + space
        self._caption_cache[key] = img
        return img

    def draw_captions(self, canvas, t):
        for ci, (s, e, idx) in enumerate(self._chunks):
            if s <= t < e:
                active = -1
                for j, wi in enumerate(idx):
                    if self.words[wi].start <= t:
                        active = j
                img = self._caption_img(ci, active)
                pop = ease_back(prog(t, s, s + 0.12))
                op = prog(t, s, s + 0.08)
                if pop < 0.999:
                    w = max(1, int(img.width * (0.88 + 0.12 * pop)))
                    h = max(1, int(img.height * (0.88 + 0.12 * pop)))
                    img = img.resize((w, h), Image.BILINEAR)
                paste(canvas, img, ((WIDTH - img.width) / 2, CAPTION_CY - img.height / 2), op)
                return

    # ============================================================ SCENE 1
    def _build_scene1(self, cache_dir):
        self.map_x, self.map_y = 40, CONTENT_TOP + 4
        bm = Image.open(basemap.render_basemap(self.build_dir.parent / "basemap.png", cache_dir)).convert("RGBA")
        bm = bm.resize((basemap.MAP_W, basemap.MAP_H))
        bm.putalpha(236)
        d = ImageDraw.Draw(bm, "RGBA")
        out, turn, inbound, remainder = basemap.flight_track()
        P = lambda ll: basemap.lonlat_to_px(ll[1], ll[0])  # noqa: E731
        # planned route, dotted
        planned = [P(p) for p in out + remainder]
        for k in range(0, len(planned) - 1, 2):
            d.line([planned[k], planned[k + 1]], fill=(220, 230, 255, 110), width=3)
        # cities
        for (lat, lon), name, col, anchor, dx in [(basemap.WARSAW, "WARSAW", CRIMSON, "lm", 18),
                                                  (basemap.DAKAR, "DAKAR · SENEGAL", (127, 168, 255), "lm", 18)]:
            x, y = P((lat, lon))
            d.ellipse([x - 10, y - 10, x + 10, y + 10], fill=WHITE, outline=col, width=4)
            d.text((x + dx, y), name, font=font("heavy", 26), fill=WHITE, anchor=anchor, stroke_width=4,
                   stroke_fill=NAVY_DEEP)
        sx, sy = P((39.6, -3.6))
        d.text((sx, sy), "SPAIN", font=font("heavy", 22), fill=(*GOLD, 230), anchor="mm", stroke_width=3,
               stroke_fill=NAVY_DEEP)
        d.text((basemap.MAP_W - 16, 16), "ILLUSTRATIVE TRACK", font=font("mono", 18), fill=(*SLATE, 230), anchor="ra")
        d.text((basemap.MAP_W - 16, 40), "PLANNED: WAW → DKR", font=font("mono", 18), fill=(220, 230, 255, 200),
               anchor="ra")
        # frame + corner brackets
        d.rectangle([0, 0, basemap.MAP_W - 1, basemap.MAP_H - 1], outline=(*GOLD, 120), width=2)
        L = 46
        for cx, cy, sx_, sy_ in [(0, 0, 1, 1), (basemap.MAP_W - 1, 0, -1, 1), (0, basemap.MAP_H - 1, 1, -1),
                                 (basemap.MAP_W - 1, basemap.MAP_H - 1, -1, -1)]:
            d.line([(cx, cy), (cx + L * sx_, cy)], fill=GOLD, width=6)
            d.line([(cx, cy), (cx, cy + L * sy_)], fill=GOLD, width=6)
        self.map_img = bm
        ox, oy = self.map_x, self.map_y
        Q = lambda ll: (ox + P(ll)[0], oy + P(ll)[1])  # noqa: E731
        self.pl_out = Polyline([Q(p) for p in out])
        self.pl_turn = Polyline([Q(out[-1])] + [Q(p) for p in turn])
        self.pl_in = Polyline([Q(p) for p in inbound])
        self.geo_out, self.geo_turn, self.geo_in = out, turn, inbound
        self.turn_px = Q(out[-1])
        # badge
        b = panel(560, 58, (*NAVY_DEEP, 230), radius=10, outline=GOLD, width=3)
        bd = ImageDraw.Draw(b)
        bd.ellipse([18, 18, 40, 40], fill=GOLD)
        bd.text((54, 29), "MOST TRACKED FLIGHT ON FLIGHTRADAR24", font=fit_font(
            "MOST TRACKED FLIGHT ON FLIGHTRADAR24", "heavy", 22, 490), fill=GOLD, anchor="lm")
        self.badge_fr24 = b
        c = panel(370, 92, (*CRIMSON, 240), radius=10)
        cd = ImageDraw.Draw(c)
        cd.text((185, 30), "U-TURN · MID-AIR", font=font("heavy", 32), fill=WHITE, anchor="mm")
        cd.text((185, 68), "OVER SOUTHERN SPAIN", font=font("bold", 24), fill=WHITE, anchor="mm")
        self.callout_turn = c

    def _geo_at(self, geo, i):
        return geo[min(i, len(geo) - 1)]

    def scene1(self, canvas, d, lt):
        op = ease_out(prog(lt, 0.0, 0.6))
        paste(canvas, self.map_img, (self.map_x, self.map_y), op)
        if op < 0.2:
            return
        # radar sweep around the map centre
        cx, cy = self.map_x + basemap.MAP_W / 2, self.map_y + basemap.MAP_H / 2
        ang = (lt * 75) % 360
        R = 620
        for k in range(10):
            a0 = ang - 3 * (k + 1)
            d.pieslice([cx - R, cy - R, cx + R, cy + R], a0, a0 + 3, fill=(242, 193, 78, int(26 * (1 - k / 10))))
        d.line([(cx, cy), (cx + R * math.cos(math.radians(ang + 3)), cy + R * math.sin(math.radians(ang + 3)))],
               fill=(242, 193, 78, 70), width=2)
        # flight progress
        p_out = ease_in_out(prog(lt, 0.6, 6.2))
        p_turn = prog(lt, 6.2, 7.6)
        p_in = ease_out(prog(lt, 7.6, 11.8))
        pts, head, hdg, gi = self.pl_out.upto(p_out)
        geo = self._geo_at(self.geo_out, gi + 1)
        if len(pts) > 1:
            d.line(pts, fill=(242, 193, 78, 90), width=14, joint="curve")
            d.line(pts, fill=GOLD, width=6, joint="curve")
        diverted = lt >= 6.2
        if diverted:
            tp, head, hdg, _ = self.pl_turn.upto(p_turn)
            ret = tp
            if lt >= 7.6:
                ip, head, hdg, gi = self.pl_in.upto(p_in)
                ret = tp + ip
                geo = self._geo_at(self.geo_in, gi + 1)
            else:
                geo = self.geo_turn[min(int(p_turn * (len(self.geo_turn) - 1)), len(self.geo_turn) - 1)]
            d.line(ret, fill=(220, 20, 60, 110), width=16, joint="curve")
            d.line(ret, fill=CRIMSON, width=8, joint="curve")
            d.line(ret, fill=WHITE, width=2, joint="curve")
        # pulse rings around the aircraft
        for k in range(3):
            ph = ((lt * 0.9) + k / 3) % 1.0
            r = 12 + 70 * ph
            d.ellipse([head[0] - r, head[1] - r, head[0] + r, head[1] + r], outline=(255, 255, 255, int(160 * (1 - ph))),
                      width=3)
        d.polygon(plane_poly(head[0] + 3, head[1] + 4, hdg, 30), fill=(0, 0, 0, 120))
        d.polygon(plane_poly(head[0], head[1], hdg, 30), fill=WHITE, outline=CRIMSON if diverted else GOLD)
        # U-turn callout
        if lt >= 6.0:
            k = ease_back(prog(lt, 6.0, 6.5))
            tx, ty = self.turn_px
            flash = 0.5 + 0.5 * math.sin(lt * 10)
            r = 26 + 10 * flash
            d.ellipse([tx - r, ty - r, tx + r, ty + r], outline=(220, 20, 60, 230), width=5)
            bx, by = tx - self.callout_turn.width / 2, ty + 95
            d.line([(tx, ty + 30), (tx, by)], fill=CRIMSON, width=4)
            img = self.callout_turn
            if k < 0.999:
                img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))))
            paste(canvas, img, (bx, by), clamp(k))
        # FR24 badge
        if lt >= 2.6:
            paste(canvas, self.badge_fr24, (self.map_x + 20, self.map_y + 20), ease_out(prog(lt, 2.6, 3.1)))
        # telemetry panel (over the empty eastern Mediterranean / Libya area)
        px0, py0 = self.map_x + basemap.MAP_W - 400, self.map_y + 330
        d.rounded_rectangle([px0, py0, px0 + 380, py0 + 330], radius=12, fill=(*NAVY_DEEP, 228),
                            outline=(*STEEL, 255), width=2)
        d.rectangle([px0, py0 + 12, px0 + 6, py0 + 318], fill=CRIMSON if diverted else GOLD)
        fm, fl = font("mono", 30), font("mono", 18)
        status = "DIVERTED → WAW" if diverted else "EN ROUTE → DKR"
        scol = CRIMSON if diverted and int(lt * 3) % 2 == 0 else (WHITE if diverted else GOLD)
        geo_hdg = basemap.bearing(geo, basemap.WARSAW) if lt >= 7.6 else (
            basemap.bearing(self.geo_out[max(0, gi - 1)], self.geo_out[min(gi + 1, len(self.geo_out) - 1)])
            if not diverted else (hdg % 360))
        dist = basemap.haversine_km(geo, basemap.WARSAW)
        rows = [("STATUS", status, scol), ("HEADING", f"{geo_hdg:03.0f}°", WHITE),
                ("DISTANCE TO WARSAW", f"{dist:,.0f} KM", WHITE), ("DATE", "30 OCT 2026", GOLD)]
        for i, (label, val, col) in enumerate(rows):
            yy = py0 + 22 + i * 77
            d.text((px0 + 26, yy + 8), label, font=fl, fill=SLATE, anchor="lm")
            d.text((px0 + 26, yy + 40), val, font=fm, fill=col, anchor="lm")

    # ============================================================ SCENE 2
    def _card(self, w, h, strip_text, strip_col, body_fill=(*NAVY_PANEL, 236)):
        img = panel(w, h, body_fill, radius=16, outline=(*STEEL, 255), width=2)
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([0, 0, w - 1, 58], radius=16, fill=strip_col)
        d.rectangle([0, 40, w - 1, 58], fill=strip_col)
        d.text((w / 2, 30), strip_text, font=fit_font(strip_text, "heavy", 26, w - 30), fill=WHITE, anchor="mm")
        return img, d

    def _build_scene2(self):
        W2, H2 = 490, 440
        left, d = self._card(W2, H2, "ACTING LEADERSHIP CLAIM", CRIMSON)
        left.alpha_composite(person_icon(96, (*WHITE, 255), CRIMSON_DARK), (W2 // 2 - 48, 76))
        d.text((W2 / 2, 200), "JUDGE ANNA", font=font("heavy", 30), fill=WHITE, anchor="mm")
        d.text((W2 / 2, 240), "KORWIN-PIOTROWSKA", font=fit_font("KORWIN-PIOTROWSKA", "heavy", 36, W2 - 40),
               fill=WHITE, anchor="mm")
        y = 290
        for line in ["Elected by parliament (Sejm)", "President refused to swear her in",
                     "Ordered Tribunal chiefs suspended"]:
            d.ellipse([28, y - 5, 38, y + 5], fill=CRIMSON)
            d.text((50, y), line, font=fit_font(line, "regular", 25, W2 - 70), fill=OFFWHITE, anchor="lm")
            y += 46
        right, d = self._card(W2, H2, "SUSPENDED LEADERSHIP", STEEL)
        right.alpha_composite(person_icon(96, (*WHITE, 255), STEEL), (W2 // 2 - 48, 76))
        d.text((W2 / 2, 205), "BOGDAN ŚWIĘCZKOWSKI", font=fit_font("BOGDAN ŚWIĘCZKOWSKI", "heavy", 34, W2 - 40),
               fill=WHITE, anchor="mm")
        d.text((W2 / 2, 243), "Tribunal President", font=font("bold", 25), fill=GOLD, anchor="mm")
        d.line([(60, 285), (W2 - 60, 285)], fill=(*STEEL, 255), width=2)
        d.text((W2 / 2, 330), "BARTŁOMIEJ SOCHAŃSKI", font=fit_font("BARTŁOMIEJ SOCHAŃSKI", "heavy", 32, W2 - 40),
               fill=WHITE, anchor="mm")
        d.text((W2 / 2, 368), "Vice-President", font=font("bold", 25), fill=GOLD, anchor="mm")
        self.s2_left, self.s2_right = shadowed(left), shadowed(right)
        # suspended stamp
        st = Image.new("RGBA", (440, 120), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rounded_rectangle([4, 4, 436, 116], radius=12, outline=CRIMSON, width=8, fill=(30, 0, 8, 120))
        sd.text((220, 60), "SUSPENDED", font=font("heavy", 64), fill=CRIMSON, anchor="mm")
        self.s2_stamp = st.resize((352, 96), Image.LANCZOS).rotate(-10, expand=True, resample=Image.BICUBIC)
        # VS badge
        vs = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        vd = ImageDraw.Draw(vs)
        vd.ellipse([0, 0, 95, 95], fill=GOLD, outline=NAVY_DEEP, width=5)
        vd.text((48, 49), "VS", font=font("heavy", 36), fill=NAVY_DEEP, anchor="mm")
        self.vs_badge = vs
        # immunity card
        W3, H3 = 1000, 218
        im = panel(W3, H3, (*NAVY_DEEP, 238), radius=16, outline=(*GOLD, 255), width=2)
        d = ImageDraw.Draw(im)
        d.rectangle([0, 14, 12, H3 - 14], fill=GOLD)
        # document icon
        d.rounded_rectangle([40, 34, 104, 114], radius=6, fill=GOLD)
        for yy in (56, 72, 88):
            d.line([(52, yy), (92, yy)], fill=NAVY_DEEP, width=5)
        d.text((128, 50), "IMMUNITY MOTION", font=font("heavy", 34), fill=GOLD, anchor="lm")
        d.text((128, 92), "Justice Minister & Prosecutor General", font=font("bold", 26), fill=SLATE, anchor="lm")
        d.text((40, 148), "WALDEMAR ŻUREK applies to lift the immunity of", font=fit_font(
            "WALDEMAR ŻUREK applies to lift the immunity of", "bold", 32, W3 - 70), fill=WHITE, anchor="lm")
        d.text((40, 190), "Święczkowski and Sochański", font=font("bold", 32), fill=WHITE, anchor="lm")
        self.s2_imm = shadowed(im)

    def scene2(self, canvas, d, lt):
        s0 = SCENES[1][0]
        fT = font("heavy", 52)
        op = ease_out(prog(lt, 0.0, 0.4))
        d.text((WIDTH / 2, CONTENT_TOP + 38), "WHO CONTROLS THE TRIBUNAL?", font=fit_font(
            "WHO CONTROLS THE TRIBUNAL?", "heavy", 54, WIDTH - 80), fill=(255, 255, 255, int(255 * op)), anchor="mm")
        d.text((WIDTH / 2, CONTENT_TOP + 88), "RIVAL CLAIMS INSIDE POLAND'S CONSTITUTIONAL TRIBUNAL",
               font=fit_font("RIVAL CLAIMS INSIDE POLAND'S CONSTITUTIONAL TRIBUNAL", "bold", 26, WIDTH - 80),
               fill=(*GOLD, int(255 * op)), anchor="mm")
        y = CONTENT_TOP + 120
        (li, pad) = self.s2_left
        k = ease_out(prog(lt, 0.15, 0.75))
        paste(canvas, li, (40 - pad - (1 - k) * 600, y - pad), k)
        (ri, pad) = self.s2_right
        k2 = ease_out(prog(lt, 0.45, 1.05))
        paste(canvas, ri, (550 - pad + (1 - k2) * 600, y - pad), k2)
        if lt > 1.0:
            kv = ease_back(prog(lt, 1.0, 1.35))
            vs = self.vs_badge.resize((max(1, int(96 * kv)), max(1, int(96 * kv))))
            paste(canvas, vs, (WIDTH / 2 - vs.width / 2, y + 124 - vs.height / 2), clamp(kv))
        t_susp = self.cue(1, ["suspended", "suspendeu"], s0 + 5.5) - s0
        if lt >= t_susp:
            ks = prog(lt, t_susp, t_susp + 0.25)
            sc = 1.6 - 0.6 * ease_out(ks)
            st = self.s2_stamp.resize((max(1, int(self.s2_stamp.width * sc)), max(1, int(self.s2_stamp.height * sc))))
            paste(canvas, st, (550 + 245 - st.width / 2, y + 124 - st.height / 2), ks)
        t_imm = self.cue(1, ["justice", "ministro"], s0 + 8.5) - s0 - 0.2
        (ii, pad) = self.s2_imm
        ki = ease_out(prog(lt, t_imm, t_imm + 0.55))
        paste(canvas, ii, (40 - pad, y + 470 - pad + (1 - ki) * 120), ki)

    # ============================================================ SCENE 3
    def _build_scene3(self):
        W, H = 1000, 330
        a = panel(W, H, (58, 8, 24, 238), radius=16, outline=(*CRIMSON, 255), width=3)
        d = ImageDraw.Draw(a)
        d.rectangle([0, 14, 14, H - 14], fill=CRIMSON)
        a.alpha_composite(person_icon(80, (*WHITE, 255), CRIMSON_DARK), (38, 24))
        d.text((136, 48), "PRESIDENT KAROL NAWROCKI", font=fit_font("PRESIDENT KAROL NAWROCKI", "heavy", 34, 830),
               fill=WHITE, anchor="lm")
        d.text((136, 88), "Head of State  •  PiS-backed", font=font("bold", 24), fill=(255, 170, 185), anchor="lm")
        d.text((W / 2, 168), "\u201cFORCIBLE TAKEOVER\u201d", font=fit_font("\u201cFORCIBLE TAKEOVER\u201d", "heavy", 80, W - 70),
               fill=WHITE, anchor="mm", stroke_width=2, stroke_fill=CRIMSON_DARK)
        d.text((W / 2, 228), "of a constitutional body", font=font("italic", 32), fill=OFFWHITE, anchor="mm")
        d.line([(60, 266), (W - 60, 266)], fill=(*CRIMSON, 160), width=2)
        d.text((W / 2, 298), "FOOTAGE: PUSHED PAST JUDGES AT THE TRIBUNAL ENTRANCE", font=fit_font(
            "FOOTAGE: PUSHED PAST JUDGES AT THE TRIBUNAL ENTRANCE", "bold", 25, W - 80), fill=GOLD, anchor="mm")
        self.s3_a = shadowed(a)
        b = panel(W, H, (12, 38, 92, 238), radius=16, outline=(*WHITE, 230), width=3)
        d = ImageDraw.Draw(b)
        d.rectangle([0, 14, 14, H - 14], fill=WHITE)
        b.alpha_composite(person_icon(80, (*WHITE, 255), (30, 70, 150)), (38, 24))
        d.text((136, 48), "PRIME MINISTER DONALD TUSK", font=fit_font("PRIME MINISTER DONALD TUSK", "heavy", 34, 830),
               fill=WHITE, anchor="lm")
        d.text((136, 88), "Head of Government  •  Civic Coalition", font=font("bold", 24), fill=(170, 200, 255),
               anchor="lm")
        d.text((W / 2, 160), "\u201cRESTORING THE RULE OF LAW\u201d", font=fit_font(
            "\u201cRESTORING THE RULE OF LAW\u201d", "heavy", 62, W - 70), fill=WHITE, anchor="mm")
        q = "\u201c\u2026after years of PiS lawlessness requires decisive action\u201d"
        d.text((W / 2, 286), q, font=fit_font(q, "italic", 28, W - 80), fill=OFFWHITE, anchor="mm")
        self.s3_b = shadowed(b)
        nc = Image.new("RGBA", (380, 64), (0, 0, 0, 0))
        nd = ImageDraw.Draw(nc)
        nd.rounded_rectangle([0, 0, 379, 63], radius=10, fill=CRIMSON, outline=WHITE, width=3)
        nd.text((190, 33), "NO COMPROMISE", font=font("heavy", 36), fill=WHITE, anchor="mm")
        self.s3_nc = nc

    def scene3(self, canvas, d, lt):
        s0 = SCENES[2][0]
        y0 = CONTENT_TOP
        # police-light strip
        flash = int(lt * 6) % 2
        d.rectangle([40, y0, WIDTH - 40, y0 + 62], fill=(*NAVY_DEEP, 235))
        for i in range(4):
            on = (i + flash) % 2 == 0
            col = (*CRIMSON, 255 if on else 70) if i < 2 else (*POLICE_BLUE, 255 if not on else 70)
            x = 40 + i * 22 if i < 2 else WIDTH - 40 - (4 - i) * 22
            d.rectangle([x, y0, x + 20, y0 + 62], fill=col)
        d.text((WIDTH / 2, y0 + 31), "RIOT POLICE SURROUND THE TRIBUNAL • PROTESTS", font=fit_font(
            "RIOT POLICE SURROUND THE TRIBUNAL • PROTESTS", "heavy", 30, WIDTH - 220), fill=WHITE, anchor="mm")
        (ai, pad) = self.s3_a
        k = ease_out(prog(lt, 0.1, 0.6))
        paste(canvas, ai, (40 - pad - (1 - k) * 500, y0 + 78 - pad), k)
        t_tusk = self.cue(2, ["tusk"], s0 + 5.5) - s0 - 0.8
        # VS divider
        vy = y0 + 78 + 330 + 30
        kv = ease_out(prog(lt, t_tusk - 0.3, t_tusk + 0.2))
        if kv > 0:
            d.line([(80, vy), (80 + (WIDTH / 2 - 140) * kv, vy)], fill=GOLD, width=3)
            d.line([(WIDTH - 80, vy), (WIDTH - 80 - (WIDTH / 2 - 140) * kv, vy)], fill=GOLD, width=3)
            paste(canvas, self.vs_badge.resize((70, 70)), (WIDTH / 2 - 35, vy - 35), kv)
        (bi, pad) = self.s3_b
        kb = ease_out(prog(lt, t_tusk, t_tusk + 0.5))
        paste(canvas, bi, (40 - pad + (1 - kb) * 500, vy + 30 - pad), kb)
        t_nc = self.cue(2, ["compromise", "acordo"], s0 + 7.5) - s0
        if lt >= t_nc:
            kn = ease_back(prog(lt, t_nc, t_nc + 0.3))
            img = self.s3_nc.resize((max(1, int(380 * kn)), max(1, int(64 * kn))))
            paste(canvas, img, (WIDTH / 2 - img.width / 2, vy + 30 + 218 - img.height / 2), clamp(kn))

    # ============================================================ SCENE 4
    TIMELINE = [
        ("2015", "Dispute over Constitutional Tribunal appointments begins"),
        ("2017", "European Commission triggers Article 7 rule-of-law procedure"),
        ("2023", "Tusk-led coalition takes power, pledging to restore the rule of law"),
        ("2025", "Karol Nawrocki sworn in as President"),
        ("OCT 2026", "Riot police cordon the Constitutional Tribunal in Warsaw"),
    ]

    def _build_scene4(self):
        # EU star ring
        ring = Image.new("RGBA", (92, 92), (0, 0, 0, 0))
        rd = ImageDraw.Draw(ring)
        rd.ellipse([0, 0, 91, 91], fill=(0, 51, 153, 255))
        for i in range(12):
            a = math.radians(i * 30 - 90)
            rd.polygon(star_points(46 + 31 * math.cos(a), 46 + 31 * math.sin(a), 7, 3), fill=(255, 204, 0))
        self.eu_ring = ring
        # end card
        W, H = 1000, 560
        ec = panel(W, H, (*NAVY_DEEP, 245), radius=22, outline=(*GOLD, 255), width=4)
        d = ImageDraw.Draw(ec)
        d.rectangle([60, 70, W - 60, 82], fill=WHITE)
        d.rectangle([60, 82, W - 60, 94], fill=CRIMSON)
        d.text((W / 2, 175), "GLOBAL NEWS 1.0", font=fit_font("GLOBAL NEWS 1.0", "heavy", 100, W - 100), fill=WHITE,
               anchor="mm")
        d.text((W / 2, 250), "NEWS IN REAL TIME", font=font("heavy", 36), fill=GOLD, anchor="mm")
        f = font("heavy", 50)
        lines = wrap("Follow Global News 1.0 for Real-Time Updates", f, W - 120)
        for i, ln in enumerate(lines):
            d.text((W / 2, 350 + i * 64), ln, font=f, fill=WHITE, anchor="mm")
        d.rounded_rectangle([W / 2 - 170, 470, W / 2 + 170, 528], radius=29, fill=CRIMSON)
        d.text((W / 2, 499), "FOLLOW  ▶", font=font("heavy", 32), fill=WHITE, anchor="mm")
        self.endcard = shadowed(ec)

    def scene4(self, canvas, d, lt):
        s0 = SCENES[3][0]
        op = ease_out(prog(lt, 0.0, 0.4))
        fT = fit_font("A DECADE-LONG RULE-OF-LAW BATTLE", "heavy", 52, WIDTH - 200)
        d.text((40, CONTENT_TOP + 36), "A DECADE-LONG RULE-OF-LAW BATTLE", font=fT, fill=(255, 255, 255, int(255 * op)),
               anchor="lm")
        d.text((40, CONTENT_TOP + 86), "WHAT IT MEANS FOR EUROPE", font=font("bold", 28), fill=(*GOLD, int(255 * op)),
               anchor="lm")
        paste(canvas, self.eu_ring, (WIDTH - 40 - 92, CONTENT_TOP + 14), op)
        x = 120
        top = CONTENT_TOP + 165
        step = 142
        n = len(self.TIMELINE)
        grow = ease_in_out(prog(lt, 0.3, 0.3 + 0.75 * n))
        d.line([(x, top), (x, top + (n - 1) * step * grow)], fill=(*SLATE, 200), width=4)
        fy, fd = font("heavy", 38), font("regular", 29)
        for i, (year, desc) in enumerate(self.TIMELINE):
            ta = 0.3 + 0.75 * i
            k = ease_out(prog(lt, ta, ta + 0.45))
            if k <= 0:
                continue
            y = top + i * step
            last = i == n - 1
            col = CRIMSON if last else GOLD
            r = 15 + (5 * (0.5 + 0.5 * math.sin(lt * 8)) if last else 0)
            if last:
                d.ellipse([x - r - 10, y - r - 10, x + r + 10, y + r + 10], outline=(*CRIMSON, 120), width=3)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(*col, int(255 * k)), outline=(255, 255, 255, int(255 * k)), width=3)
            dx = (1 - k) * 60
            d.text((x + 44 + dx, y - 16), year, font=fy, fill=(*col, int(255 * k)), anchor="lm")
            lines = wrap(desc, fd, WIDTH - x - 100)
            for j, ln in enumerate(lines[:2]):
                d.text((x + 44 + dx, y + 26 + j * 34), ln, font=fd, fill=(*OFFWHITE, int(255 * k)), anchor="lm")
        t_end = self.cue(3, ["follow", "siga"], s0 + 8.5) - s0 - 0.25
        if lt >= t_end:
            ke = ease_out(prog(lt, t_end, t_end + 0.5))
            d.rectangle([0, CONTENT_TOP - 4, WIDTH, CONTENT_BOTTOM + 4], fill=(*NAVY_DEEP, int(170 * ke)))
            (ei, pad) = self.endcard
            paste(canvas, ei, (40 - pad, CONTENT_TOP + 150 - pad + (1 - ke) * 80), ke)

    # ------------------------------------------------------------ transitions
    def draw_transition(self, d, t):
        for s0, _ in SCENES[1:]:
            p = (t - (s0 - 0.22)) / 0.44
            if 0 <= p <= 1:
                x = -300 + (WIDTH + 600) * ease_in_out(p)
                d.polygon([(x - 260, CONTENT_TOP), (x + 40, CONTENT_TOP), (x - 60, CONTENT_BOTTOM),
                           (x - 360, CONTENT_BOTTOM)], fill=(*CRIMSON, 235))
                d.polygon([(x + 40, CONTENT_TOP), (x + 100, CONTENT_TOP), (x, CONTENT_BOTTOM),
                           (x - 60, CONTENT_BOTTOM)], fill=(255, 255, 255, 235))

    # ------------------------------------------------------------------ frame
    def frame(self, t, broll_frame=None):
        canvas = self.base_frame(broll_frame)
        d = ImageDraw.Draw(canvas, "RGBA")
        si = next(i for i, (a, b) in enumerate(SCENES) if t < b or i == len(SCENES) - 1)
        lt = t - SCENES[si][0]
        [self.scene1, self.scene2, self.scene3, self.scene4][si](canvas, d, lt)
        self.draw_transition(d, t)
        self.draw_header(canvas, d, t)
        self.draw_captions(canvas, t)
        self.draw_ticker(canvas, d, t)
        return canvas

    def render(self, mix_wav: Path, out_mp4: Path, preview_times=()):
        broll = BrollReader(self.assets) if self.assets else None
        if self.assets:
            print(f"  [b-roll] compositing {len(self.assets)} asset(s): {', '.join(a.name for a in self.assets)}")
        cmd = [ffmpeg_bin(), "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{WIDTH}x{HEIGHT}",
               "-r", str(FPS), "-i", "-", "-i", str(mix_wav), "-map", "0:v", "-map", "1:a",
               "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-profile:v", "high",
               "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", str(DURATION),
               "-movflags", "+faststart", str(out_mp4)]
        enc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        total = int(DURATION * FPS)
        previews = {int(round(pt * FPS)): pt for pt in preview_times}
        try:
            for fi in range(total):
                t = fi / FPS
                img = self.frame(t, broll.next() if broll else None)
                enc.stdin.write(img.tobytes())
                if fi in previews:
                    img.save(self.build_dir / f"preview_{previews[fi]:05.2f}s.png")
                if fi % (FPS * 5) == 0:
                    print(f"  [render] {t:5.1f}s / {DURATION:.0f}s")
        finally:
            enc.stdin.close()
            enc.wait()
            if broll:
                broll.close()
        if enc.returncode != 0:
            raise RuntimeError("FFmpeg encode failed")
        return out_mp4
