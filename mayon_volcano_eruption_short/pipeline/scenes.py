"""Per-frame compositor: disaster-monitoring-desk chrome + four animated scenes.

Every frame is a pure function of its timestamp, so frames can be rendered
in parallel worker processes.
"""
from __future__ import annotations

import math
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import config as C
from . import graphics as G
from .captions import CaptionRenderer
from .content import CONTENT

# ---------------------------------------------------------------- easing ---


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = clamp(x)
    return 3 * x * x - 2 * x * x * x


def ease_back(x):
    x = clamp(x)
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def rgba(c, a):
    return tuple(c[:3]) + (int(clamp(a, 0, 1) * 255),)


def count_fmt(template: str, frac: float, start: int = 0) -> str:
    """Animate the first number inside *template* from *start* to its value."""
    m = re.search(r"\d[\d.,]*", template)
    if not m:
        return template
    raw = m.group(0)
    sep = "," if "," in raw else ("." if "." in raw else "")
    target = int(re.sub(r"[.,]", "", raw))
    val = int(round(start + (target - start) * clamp(frac)))
    s = f"{val:,}".replace(",", sep) if sep else str(val)
    return template[:m.start()] + s + template[m.end():]


def _norm(w: str) -> str:
    return w.lower().strip(".,!?;:\"'()")


# ------------------------------------------------------------- renderer ---
class Renderer:
    def __init__(self, lang: str, words, has_broll: bool):
        self.lang = lang
        self.ui = CONTENT[lang]["ui"]
        self.cue_words = CONTENT[lang]["cues"]
        self.words = words
        self.has_broll = has_broll
        self.captions = CaptionRenderer(words)
        self._sprites: dict = {}

        self.chart, self.chart_px = G.volcano_chart(self.ui, size=(1000, 700))
        self.map_img, self.map_px, _ = G.albay_map(self.ui)

        self._build_static()
        self._build_particles()
        self.cues = {k: self._cue(k) for k in self.cue_words}

    # ............................................................ helpers
    def _cue(self, key):
        target = _norm(self.cue_words[key])
        for w in self.words:
            if _norm(w.text).startswith(target) or _norm(w.text.split(" ")[0]) == target:
                return w.start
        return None

    def cue_lt(self, key, scene, default, after=0.0):
        """Cue time relative to scene start (falls back to *default*)."""
        s0, s1 = C.SCENES[scene]
        target = _norm(self.cue_words[key])
        for w in self.words:
            if s0 + after <= w.start < s1 and (_norm(w.text).startswith(target)):
                return w.start - s0
        return default

    def text_w(self, s, f):
        return f.getlength(s)

    def glow_sprite(self, key, text, f, color, radius=10, strength=2):
        k = ("glow", key)
        if k not in self._sprites:
            w = int(f.getlength(text)) + radius * 6
            asc, desc = f.getmetrics()
            h = asc + desc + radius * 6
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            d = ImageDraw.Draw(img)
            d.text((radius * 3, radius * 3), text, font=f, fill=rgba(color, 1))
            glow = img.filter(ImageFilter.GaussianBlur(radius))
            out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            for _ in range(strength):
                out.alpha_composite(glow)
            out.alpha_composite(img)
            self._sprites[k] = (out, radius * 3)
        return self._sprites[k]

    def radial_sprite(self, key, size, color, power=2.0, alpha=1.0):
        k = ("radial", key)
        if k not in self._sprites:
            yy, xx = np.mgrid[0:size, 0:size]
            r = np.hypot(xx - size / 2, yy - size / 2) / (size / 2)
            a = np.clip(1 - r, 0, 1) ** power * 255 * alpha
            arr = np.zeros((size, size, 4), np.uint8)
            arr[..., :3] = color[:3]
            arr[..., 3] = a.astype(np.uint8)
            self._sprites[k] = Image.fromarray(arr, "RGBA")
        return self._sprites[k]

    @staticmethod
    def with_alpha(img: Image.Image, k: float) -> Image.Image:
        if k >= 0.999:
            return img
        out = img.copy()
        a = out.getchannel("A").point(lambda v: int(v * k))
        out.putalpha(a)
        return out

    def panel(self, d, box, title=None, accent=C.ORANGE, fill_a=None):
        x0, y0, x1, y1 = box
        if fill_a is None:
            fill_a = 0.62 if self.has_broll else 0.82
        d.rounded_rectangle(box, radius=22, fill=rgba(C.ASH, fill_a),
                            outline=rgba(C.ASH_3, 1), width=2)
        L = 34
        for (cx, cy, sx, sy) in [(x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)]:
            d.line([(cx + sx * 6, cy + sy * (L + 6)), (cx + sx * 6, cy + sy * 6),
                    (cx + sx * (L + 6), cy + sy * 6)], fill=rgba(accent, 1), width=5)
        if title:
            d.text((x0 + 28, y0 + 18), title, font=C.font("mono", 22), fill=rgba(C.GRAY, 1))

    # ....................................................... static layers
    def _build_static(self):
        W, H = C.W, C.H
        yy = np.linspace(0, 1, H)[:, None]
        xx = np.linspace(-1, 1, W)[None, :]
        rng = np.random.default_rng(3)

        # procedural charcoal background (used when there is no B-roll)
        base = np.zeros((H, W, 3), np.float32)
        top, bot = np.array(C.ASH, np.float32), np.array((30, 24, 22), np.float32)
        base[:] = top * (1 - yy[..., None]) + bot * yy[..., None]
        glow = np.exp(-((xx ** 2) / 0.5 + ((yy - 1.05) ** 2) / 0.10))[..., None]
        base += glow * np.array([70, 22, 0], np.float32)
        # faint telemetry grid
        grid = np.zeros((H, W), np.float32)
        grid[::60, :] = 1
        grid[:, ::60] = 1
        base += grid[..., None] * 5
        base += rng.normal(0, 4.0, (H, W, 1)).astype(np.float32)   # film grain
        self.bg_base = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8), "RGB")

        # scrim used on top of B-roll: darker top/bottom, lets centre breathe
        a = 0.30 + 0.50 * np.clip(np.abs(yy - 0.45) / 0.45, 0, 1) ** 1.6
        scrim = np.zeros((H, W, 4), np.uint8)
        scrim[..., :3] = C.ASH
        scrim[..., 3] = (np.broadcast_to(a, (H, W)) * 255).astype(np.uint8)
        self.scrim = Image.fromarray(scrim, "RGBA")

        # broadcast vignette
        r = np.sqrt(xx ** 2 * 0.9 + ((yy - 0.5) * 2) ** 2 * 0.55)
        va = np.clip((r - 0.55) / 0.75, 0, 1) ** 1.6 * 200
        vig = np.zeros((H, W, 4), np.uint8)
        vig[..., 3] = va.astype(np.uint8)
        self.vignette = Image.fromarray(vig, "RGBA")

        # static chrome: header band, info strip, footer
        chrome = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(chrome)
        d.rectangle((0, 0, W, C.HEADER_BOTTOM), fill=rgba(C.ASH, 0.94))
        d.rectangle((0, C.HEADER_BOTTOM, W, C.HEADER_BOTTOM + 5), fill=rgba(C.ORANGE, 1))
        d.rectangle((0, C.HEADER_BOTTOM + 5, W, C.HEADER_BOTTOM + 46), fill=rgba((12, 12, 14), 0.9))
        live_f = C.font("bold", 28)
        self.live_w = int(live_f.getlength(self.ui["live"])) + 62
        hx = 40 + self.live_w + 18
        f1 = C.fit_font("bold", self.ui["header_1"], W - hx - 40, 40)
        d.text((hx, 108), self.ui["header_1"], font=f1, fill=rgba(C.WHITE, 1), anchor="lm")
        f2 = C.fit_font("display", self.ui["header_2"], W - 80, 92)
        spr, pad = self.glow_sprite("h2", self.ui["header_2"], f2, C.ORANGE, radius=12, strength=1)
        chrome.alpha_composite(spr, (40 - pad, 140 - pad))
        fi = C.fit_font("mono", self.ui["info"], W - 80, 22)
        d.text((40, C.INFO_Y), self.ui["info"], font=fi, fill=rgba(C.GRAY, 1))
        ff = C.font("mono", 20)
        d.text((W // 2, C.FOOTER_Y + 12), self.ui["footer"], font=ff, fill=rgba(C.GRAY_DIM, 1),
               anchor="mm")
        self.chrome = chrome

        # ticker strip sprite (text repeated twice for seamless wrap)
        tf = C.font("bold", 30)
        txt = self.ui["ticker"]
        tw = int(tf.getlength(txt))
        strip = Image.new("RGBA", (tw * 2, C.TICKER_Y1 - C.TICKER_Y0), (0, 0, 0, 0))
        sd = ImageDraw.Draw(strip)
        for k in range(2):
            sd.text((k * tw, (C.TICKER_Y1 - C.TICKER_Y0) // 2), txt, font=tf,
                    fill=rgba(C.WHITE, 1), anchor="lm")
        self.ticker_strip, self.ticker_w = strip, tw

        # scanline trail for the map
        trail = np.zeros((140, 1000, 4), np.uint8)
        trail[..., :3] = C.ORANGE
        trail[..., 3] = (np.linspace(0, 1, 140) ** 2 * 90)[:, None].astype(np.uint8)
        self.scan_trail = Image.fromarray(trail, "RGBA")

        # hazard stripes tile (scene 3)
        hz = Image.new("RGBA", (120, 172), rgba(C.SULFUR, 1))
        hd = ImageDraw.Draw(hz)
        for k in range(-10, 20):
            x = k * 30
            hd.polygon([(x, 0), (x + 15, 0), (x + 15 - 172, 172), (x - 172, 172)], fill=rgba((18, 18, 18), 1))
        self.hazard_tile = hz

    def _build_particles(self):
        rng = np.random.default_rng(11)
        n = 420
        self.pl = dict(u0=rng.random(n), speed=rng.uniform(0.055, 0.12, n),
                       ang=rng.uniform(0, 2 * np.pi, n), wob=rng.uniform(0.4, 1.4, n),
                       size=rng.uniform(0.6, 1.35, n), shade=rng.random(n),
                       hot=rng.random(n))
        nb = 46
        self.ballistic = dict(t0=rng.uniform(0.6, 3.6, nb), vx=rng.uniform(-1.9, 1.9, nb),
                              vy=rng.uniform(500, 1100, nb), size=rng.uniform(3, 6, nb))
        nf = 80
        self.flakes = dict(x=rng.uniform(0, C.W, nf), y=rng.uniform(0, C.H, nf),
                           vx=rng.uniform(-14, 26, nf), vy=rng.uniform(18, 60, nf),
                           r=rng.uniform(1.2, 3.6, nf), a=rng.uniform(0.25, 0.6, nf),
                           ph=rng.uniform(0, 6.28, nf))

    # ............................................................. frame
    def frame(self, i: int, bg: Image.Image | None = None) -> Image.Image:
        t = i / C.FPS
        if bg is not None:
            cv = bg.copy()
            cv.paste(self.scrim, (0, 0), self.scrim)
        else:
            cv = self.bg_base.copy()
        d = ImageDraw.Draw(cv, "RGBA")
        self._flakes(d, t)
        cv.paste(self.vignette, (0, 0), self.vignette)
        cv.paste(self.chrome, (0, 0), self.chrome)
        self._dynamic_chrome(cv, d, t)

        k = next(idx for idx, (s, e) in enumerate(C.SCENES) if t < e or idx == len(C.SCENES) - 1)
        s0, s1 = C.SCENES[k]
        lt = t - s0
        a_in = ease_out(lt / 0.4) if k > 0 else ease_out(lt / 0.25)
        a_out = 1 - ease_in_out((lt - (s1 - s0 - 0.28)) / 0.28) if k < 3 else 1.0
        alpha = min(a_in, a_out)
        oy = int((1 - a_in) * 50)
        before = cv.copy() if alpha < 0.999 else None
        getattr(self, f"scene{k + 1}")(cv, d, lt, oy)
        if before is not None:
            cv = Image.blend(before, cv, alpha)
            d = ImageDraw.Draw(cv, "RGBA")

        self.captions.draw(cv, t)
        self._ticker(cv, d, t)
        cv = self._fx(cv, t)
        return cv

    # .................................................. shared overlays
    def _flakes(self, d, t):
        f = self.flakes
        x = (f["x"] + f["vx"] * t + 22 * np.sin(t * 0.8 + f["ph"])) % C.W
        y = (f["y"] + f["vy"] * t) % C.H
        for xi, yi, ri, ai in zip(x, y, f["r"], f["a"]):
            d.ellipse((xi - ri, yi - ri, xi + ri, yi + ri), fill=rgba((175, 170, 165), ai))

    def _dynamic_chrome(self, cv, d, t):
        # LIVE pill with blinking dot
        x0, y0 = 40, 86
        d.rounded_rectangle((x0, y0, x0 + self.live_w, y0 + 46), radius=10, fill=rgba(C.RED, 1))
        on = (t % 1.0) < 0.6
        d.ellipse((x0 + 16, y0 + 15, x0 + 32, y0 + 31), fill=rgba(C.WHITE, 1 if on else 0.25))
        d.text((x0 + 44, y0 + 23), self.ui["live"], font=C.font("bold", 28),
               fill=rgba(C.WHITE, 1), anchor="lm")
        # story-style progress segments
        gap, y = 10, C.PROGRESS_Y
        segw = (C.W - 80 - gap * 3) / 4
        for k, (s, e) in enumerate(C.SCENES):
            xa = 40 + k * (segw + gap)
            d.rounded_rectangle((xa, y, xa + segw, y + 6), radius=3, fill=rgba(C.WHITE, 0.18))
            p = clamp((t - s) / (e - s))
            if p > 0:
                col = C.ORANGE if s <= t < e else C.WHITE
                d.rounded_rectangle((xa, y, xa + segw * p, y + 6), radius=3, fill=rgba(col, 1))
        # scene chip
        k = min(3, next((idx for idx, (s, e) in enumerate(C.SCENES) if t < e), 3))
        f = C.font("mono", 26)
        label = self.ui["chips"][k]
        w = f.getlength(label)
        d.rounded_rectangle((40, C.CHIP_Y, 40 + w + 36, C.CHIP_Y + 44), radius=8,
                            fill=rgba(C.ORANGE, 0.16), outline=rgba(C.ORANGE, 1), width=2)
        d.text((58, C.CHIP_Y + 22), label, font=f, fill=rgba(C.ORANGE_HOT, 1), anchor="lm")
        rf = C.font("mono", 22)
        rl = self.ui["chip_right"][k]
        d.text((C.W - 40, C.CHIP_Y + 22), rl, font=rf, fill=rgba(C.GRAY, 1), anchor="rm")
        rw = rf.getlength(rl)
        blink = 0.5 + 0.5 * math.sin(t * 6)
        cx = C.W - 40 - rw - 18
        d.ellipse((cx - 6, C.CHIP_Y + 16, cx + 6, C.CHIP_Y + 28), fill=rgba(C.RED, 0.4 + 0.6 * blink))

    def _ticker(self, cv, d, t):
        y0, y1 = C.TICKER_Y0, C.TICKER_Y1
        d.rectangle((0, y0, C.W, y1), fill=rgba((14, 14, 16), 0.92))
        d.rectangle((0, y0, C.W, y0 + 3), fill=rgba(C.ORANGE, 1))
        tag_f = C.font("display", 30)
        tag = self.ui["ticker_tag"]
        tw = int(tag_f.getlength(tag)) + 48
        off = int((t * 165) % self.ticker_w)
        crop = self.ticker_strip.crop((off, 0, off + C.W - tw, y1 - y0))
        cv.paste(crop, (tw, y0), crop)
        d.rectangle((0, y0, tw, y1), fill=rgba(C.ORANGE, 1))
        d.polygon([(tw, y0), (tw + 18, (y0 + y1) // 2), (tw, y1)], fill=rgba(C.ORANGE, 1))
        d.text((24, (y0 + y1) // 2), tag, font=tag_f, fill=rgba(C.ASH, 1), anchor="lm")

    def _fx(self, cv, t):
        # eruption flash on the hook
        if 0.30 <= t < 0.95:
            a = (1 - (t - 0.30) / 0.65) ** 2 * 0.55
            cv = Image.blend(cv, Image.new("RGB", cv.size, (255, 196, 140)), a)
        # glitch slices on scene cuts
        for s, _ in C.SCENES[1:]:
            if abs(t - s) < 0.12:
                rng = np.random.default_rng(int(t * 1000))
                for _ in range(7):
                    y = int(rng.integers(C.PANEL_TOP, C.PANEL_BOTTOM - 40))
                    h = int(rng.integers(8, 46))
                    dx = int(rng.integers(-42, 42))
                    band = cv.crop((0, y, C.W, y + h))
                    cv.paste(band, (dx, y))
                d = ImageDraw.Draw(cv, "RGBA")
                yl = int(rng.integers(C.PANEL_TOP, C.PANEL_BOTTOM))
                d.rectangle((0, yl, C.W, yl + 4), fill=rgba(C.ORANGE, 0.9))
        return cv

    # ======================================================= SCENE 1 ===
    def scene1(self, cv, d, lt, oy):
        ui = self.ui
        box = (C.PANEL_X0, C.PANEL_TOP + oy, C.PANEL_X1, C.PANEL_BOTTOM + oy)
        self.panel(d, box, ui["s1_panel"])

        # eruption shake
        dx = dy = 0
        if 0.35 < lt < 1.8:
            amp = 11 * (1 - (lt - 0.35) / 1.45) ** 2
            dx = int(amp * math.sin(lt * 91))
            dy = int(amp * math.cos(lt * 77))
        x0, y0 = C.PANEL_X0 + dx, C.PANEL_TOP + 48 + oy + dy
        cv.paste(self.chart, (x0, y0), self.chart)

        def sp(xkm, ym):
            px, py = self.chart_px(xkm, ym)
            return x0 + px, y0 + py

        H = 3000 * ease_out((lt - 0.45) / 5.2)
        if lt > 5.65:
            H = 3000 + 35 * math.sin((lt - 5.65) * 1.7)
        g = clamp(H / 3000)

        # crater glow
        cx, cy = sp(0, G.SUMMIT_M)
        glow = self.radial_sprite("crater", 220, C.LAVA, power=1.8)
        k = 0.55 + 0.25 * math.sin(lt * 7) + 0.2 * clamp((lt - 0.4) * 3)
        gs = self.with_alpha(glow, clamp(k))
        cv.paste(gs, (int(cx - 110), int(cy - 110)), gs)

        # ash fall curtain downwind
        if lt > 4.0:
            a = clamp((lt - 4.0) / 2.0) * 0.09
            top_y = sp(0, G.SUMMIT_M + H * 0.88)[1]
            pts = [sp(0.8, 0)[0], sp(4.2, 0)[0]]
            d.polygon([(sp(0.6, 0)[0], top_y), (sp(3.6, 0)[0], top_y + 20),
                       (pts[1] + 40, sp(0, 300)[1]), (pts[0], sp(0, 300)[1])],
                      fill=rgba((150, 146, 140), a))

        self._plume(cv, sp, lt, H, g)
        self._ballistics(d, sp, lt)

        # dimension line: 3,000 m above crater rim
        if H > 40:
            xd = sp(4.7, 0)[0]
            yb = sp(0, G.SUMMIT_M)[1]
            yt = sp(0, G.SUMMIT_M + H)[1]
            dash_col = rgba(C.WHITE, 0.55)
            for xx in range(int(cx + 18), int(xd) - 6, 16):
                d.line([(xx, yt), (xx + 8, yt)], fill=dash_col, width=2)
                d.line([(xx, yb), (xx + 8, yb)], fill=dash_col, width=2)
            d.line([(xd, yb), (xd, yt)], fill=rgba(C.WHITE, 1), width=4)
            d.line([(xd - 14, yb), (xd + 14, yb)], fill=rgba(C.WHITE, 1), width=4)
            d.polygon([(xd - 13, yt + 22), (xd + 13, yt + 22), (xd, yt)], fill=rgba(C.SULFUR, 1))
            settled = lt > 5.6
            m = 3000 if settled else int(round(H / 10.0) * 10)
            ft = 9840 if settled else int(round(9840 * H / 3000 / 10.0) * 10)
            sep = "," if self.lang == "en" else "."
            mtxt = f"{m:,} m".replace(",", sep)
            ftxt = f"{ft:,} FT".replace(",", sep)
            ym = clamp((yb + yt) / 2 - 70, C.PANEL_TOP + 120 + oy, C.PANEL_BOTTOM - 200)
            lx = xd + 24
            d.text((lx, ym), "+" + mtxt, font=C.font("display", 62), fill=rgba(C.WHITE, 1))
            d.text((lx + 4, ym + 76), ftxt, font=C.font("mono", 36), fill=rgba(C.SULFUR, 1))
            d.text((lx + 4, ym + 122), self.ui["s1_above"], font=C.font("mono", 20),
                   fill=rgba(C.GRAY, 1))

        # eruption time stamp
        if lt > 0.8:
            a = ease_out((lt - 0.8) / 0.4)
            xr = C.PANEL_X1 - 26
            yy = C.PANEL_TOP + 16 + oy
            f = C.font("mono", 22)
            tw = f.getlength(ui["s1_time"])
            d.text((xr, yy), ui["s1_time"], font=f, fill=rgba(C.WHITE, a), anchor="ra")
            pulse = 0.5 + 0.5 * math.sin(lt * 8)
            d.ellipse((xr - tw - 26, yy + 5, xr - tw - 12, yy + 19), fill=rgba(C.RED, a * (0.4 + 0.6 * pulse)))
            d.text((xr, yy + 30), ui["s1_type"], font=C.font("mono", 20),
                   fill=rgba(C.ORANGE_HOT, a), anchor="ra")

        self._alert_badge(cv, d, lt, oy)

    def _plume(self, cv, sp, lt, H, g):
        if H < 5:
            return
        p = self.pl
        u = (p["u0"] + lt * p["speed"]) % 1.0
        h = u * H
        r = 0.16 + 0.42 * u + 2.0 * np.clip((u - 0.72) / 0.28, 0, 1) ** 1.6
        drift = 1.0 * u ** 2.2 * g
        x = drift + r * np.sin(p["ang"] + lt * 0.6 * p["wob"])
        y = G.SUMMIT_M + h - 260 * np.clip((u - 0.85) / 0.15, 0, 1) * (np.cos(p["ang"]) ** 2)
        rad = (8 + 24 * u ** 0.8) * p["size"] * (0.35 + 0.65 * g)

        # region layer around the column
        lx0, ly0 = sp(-4.6, G.SUMMIT_M + 3700)
        lx1, ly1 = sp(5.4, G.SUMMIT_M - 250)
        lx0, ly0, lx1, ly1 = int(lx0), int(ly0), int(lx1), int(ly1)
        lw, lh = lx1 - lx0, ly1 - ly0
        soft = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
        sd = ImageDraw.Draw(soft)
        order = np.argsort(np.cos(p["ang"] + lt * 0.6 * p["wob"]))   # back → front
        for j in order:
            px, py = sp(x[j], y[j])
            px -= lx0
            py -= ly0
            rr = rad[j]
            v = int(52 + 52 * p["shade"][j] + 34 * u[j])
            if u[j] < 0.12 and p["hot"][j] > 0.55:
                col = (255, int(90 + 80 * p["shade"][j]), 30, 255)
            else:
                col = (v + 6, v + 2, v, 255)
            sd.ellipse((px - rr, py - rr, px + rr, py + rr), fill=col)
            hr = rr * 0.55
            hv = min(255, v + 38)
            sd.ellipse((px - rr * 0.35 - hr, py - rr * 0.4 - hr, px - rr * 0.35 + hr, py - rr * 0.4 + hr),
                       fill=(hv, hv - 2, hv - 6, 255))
        soft = soft.filter(ImageFilter.GaussianBlur(5))
        cv.paste(soft, (lx0, ly0), soft)

    def _ballistics(self, d, sp, lt):
        b = self.ballistic
        for t0, vx, vy, sz in zip(b["t0"], b["vx"], b["vy"], b["size"]):
            tau = lt - t0
            if tau <= 0:
                continue
            gacc = 900.0
            xk = vx * tau
            ym = G.SUMMIT_M + vy * tau - 0.5 * gacc * tau * tau
            if ym < G.cone_profile(np.array([xk]))[0] or tau > 3.5:
                continue
            px, py = sp(xk, ym)
            pxp, pyp = sp(vx * (tau - 0.08), G.SUMMIT_M + vy * (tau - 0.08) - 0.5 * gacc * (tau - 0.08) ** 2)
            d.line([(pxp, pyp), (px, py)], fill=rgba(C.ORANGE, 0.7), width=int(sz * 0.7))
            d.ellipse((px - sz, py - sz, px + sz, py + sz), fill=rgba(C.SULFUR, 1))

    def _alert_badge(self, cv, d, lt, oy):
        t_in, t_flip = 6.0, 6.9
        if lt < t_in:
            return
        ui = self.ui
        slide = ease_out((lt - t_in) / 0.45)
        flipped = lt >= t_flip
        bw, bh = 300, 150
        bx = int(C.PANEL_X0 + 112 - (1 - slide) * 380)
        by = C.PANEL_TOP + 86 + oy
        col = C.ORANGE if flipped else C.SULFUR
        if flipped:
            pulse = 0.5 + 0.5 * math.sin((lt - t_flip) * 6)
            gl = self.radial_sprite("badge", 520, C.ORANGE, power=2.2)
            gls = self.with_alpha(gl, 0.35 + 0.4 * pulse)
            cv.paste(gls, (bx + bw // 2 - 260, by + bh // 2 - 260), gls)
        pop = 1.0
        if flipped and lt - t_flip < 0.25:
            pop = 1 + 0.12 * math.sin((lt - t_flip) / 0.25 * math.pi)
        w2, h2 = bw * pop, bh * pop
        bx2, by2 = bx + (bw - w2) / 2, by + (bh - h2) / 2
        d.rounded_rectangle((bx2, by2, bx2 + w2, by2 + h2), radius=16, fill=rgba(col, slide))
        d.rounded_rectangle((bx2 + 6, by2 + 6, bx2 + w2 - 6, by2 + h2 - 6), radius=12,
                            outline=rgba(C.ASH, 0.6 * slide), width=2)
        dark = rgba(C.ASH, slide)
        d.text((bx2 + 18, by2 + 14), ui["alert_org"], font=C.font("mono", 20), fill=dark)
        lf = C.fit_font("display", ui["alert_lbl"], 190, 34)
        d.text((bx2 + 18, by2 + 42), ui["alert_lbl"], font=lf, fill=dark)
        d.text((bx2 + w2 - 22, by2 + h2 / 2 + 4), "3" if flipped else "2",
               font=C.font("display", int(118 * pop)), fill=dark, anchor="rm")
        if flipped:
            ff = C.fit_font("mono", ui["alert_from"], 190, 17)
            d.text((bx2 + 18, by2 + h2 - 38), ui["alert_from"], font=ff, fill=dark)
            if lt - t_flip < 0.18:
                d.rounded_rectangle((bx2, by2, bx2 + w2, by2 + h2), radius=16,
                                    fill=rgba(C.WHITE, 0.7 * (1 - (lt - t_flip) / 0.18)))

    # ======================================================= SCENE 2 ===
    MAP_WIN_H = 704
    MAP_CROP_Y = 36

    def scene2(self, cv, d, lt, oy):
        ui = self.ui
        box = (C.PANEL_X0, C.PANEL_TOP + oy, C.PANEL_X1, C.PANEL_BOTTOM + oy)
        self.panel(d, box, ui["s2_panel"])
        wx0, wy0 = C.PANEL_X0, C.PANEL_TOP + 50 + oy
        ww, wh = 1000, self.MAP_WIN_H
        z = 1.0 + 0.12 * ease_in_out(lt / 13.0)
        s0 = ww / self.map_img.width
        mx, my = self.map_px(0, 0)
        crop_x = mx * s0 * (z - 1)
        crop_y = my * s0 * (z - 1) + self.MAP_CROP_Y
        sc = s0 * z
        win = self.map_img.transform((ww, wh), Image.AFFINE,
                                     (1 / sc, 0, crop_x / sc, 0, 1 / sc, crop_y / sc),
                                     resample=Image.BILINEAR)
        cv.paste(win, (wx0, wy0), win)

        def sp(xk, yk):
            px, py = self.map_px(xk, yk)
            return wx0 + px * sc - crop_x, wy0 + py * sc - crop_y

        ppk = sc * self.map_img.width / (G.MAP_X1 - G.MAP_X0)   # px per km
        cx, cy = sp(0, 0)
        # crosshair
        d.line([(wx0, cy), (wx0 + ww, cy)], fill=rgba(C.WHITE, 0.10), width=1)
        d.line([(cx, wy0), (cx, wy0 + wh)], fill=rgba(C.WHITE, 0.10), width=1)

        # labels
        gx, gy = sp(12.0, -3.5)
        d.text((gx, gy), ui["gulf"], font=C.font("mono", 22), fill=rgba((150, 175, 185), 0.75), anchor="mm")
        lx, ly = sp(*G.LEGAZPI)
        if ly < wy0 + wh - 14:
            d.ellipse((lx - 6, ly - 6, lx + 6, ly + 6), fill=rgba(C.GRAY, 1))
            d.text((lx + 12, ly), ui["legazpi"], font=C.font("mono", 18), fill=rgba(C.GRAY, 1), anchor="lm")
        d.text((wx0 + 18, wy0 + 14), "13.2575°N  123.6856°E", font=C.font("mono", 20),
               fill=rgba(C.WHITE, 0.75))

        # scanline sweep
        if 0.1 < lt < 1.7:
            ys = wy0 + wh * ease_in_out((lt - 0.1) / 1.6)
            tr = self.scan_trail
            top = int(ys - tr.height)
            if top < wy0:
                tr = tr.crop((0, wy0 - top, tr.width, tr.height))
                top = wy0
            if tr.height > 0:
                cv.paste(tr, (wx0, top), tr)
            d.line([(wx0, ys), (wx0 + ww, ys)], fill=rgba(C.ORANGE_HOT, 1), width=3)

        # PDZ perimeter
        p = ease_in_out((lt - 0.8) / 1.3)
        R = 6.0 * ppk
        if p > 0:
            if p >= 1:
                fa = 0.12 + 0.05 * math.sin(lt * 3)
                d.ellipse((cx - R, cy - R, cx + R, cy + R), fill=rgba(C.ORANGE, fa))
                # radar sweep wedge
                th = (lt * 110) % 360
                for kk in range(10):
                    d.pieslice((cx - R, cy - R, cx + R, cy + R), th - 4 * (kk + 1), th - 4 * kk,
                               fill=rgba(C.ORANGE_HOT, 0.22 * (1 - kk / 10)))
                # expanding pulse ring
                ph = (lt % 2.0) / 2.0
                rr = R * (1 + 0.28 * ph)
                d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=rgba(C.ORANGE, 0.6 * (1 - ph)), width=3)
            rot = lt * 10
            end = 360 * p
            a = 0.0
            while a < end:
                seg = min(7.0, end - a)
                d.arc((cx - R, cy - R, cx + R, cy + R), -90 + a + rot, -90 + a + seg + rot,
                      fill=rgba(C.ORANGE, 1), width=6)
                a += 11.0
        # Mayon marker
        pulse = (lt % 1.2) / 1.2
        rr = 10 + 26 * pulse
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=rgba(C.RED, 1 - pulse), width=3)
        d.polygon([(cx, cy - 14), (cx - 13, cy + 9), (cx + 13, cy + 9)], fill=rgba(C.WHITE, 1),
                  outline=rgba(C.RED, 1))
        d.text((cx + 20, cy - 26), "MAYON", font=C.font("bold", 26), fill=rgba(C.WHITE, 1))
        if (lt % 0.8) < 0.55:
            d.text((cx + 20, cy + 4), "2,463 m" if self.lang == "en" else "2.463 m",
                   font=C.font("mono", 18), fill=rgba(C.ORANGE_HOT, 1))
        if p >= 1:
            a = ease_out((lt - 2.1) / 0.4)
            f = C.fit_font("mono", ui["pdz_label"], 600, 21)
            tx, ty = cx, cy + R + 26
            tw = f.getlength(ui["pdz_label"])
            d.rounded_rectangle((tx - tw / 2 - 14, ty - 18, tx + tw / 2 + 14, ty + 18), radius=8,
                                fill=rgba(C.ORANGE, a))
            d.text((tx, ty), ui["pdz_label"], font=f, fill=rgba(C.ASH, a), anchor="mm")

        # evacuation corridors + hubs (synced to narration)
        defaults = {"tabaco": 7.0, "camalig": 8.5, "ligao": 9.8}
        label_pos = {"tabaco": "left", "camalig": "right", "ligao": "below"}
        for name, (tx_km, ty_km) in G.TOWNS.items():
            t0 = self.cue_lt(name, 1, defaults[name]) - 0.25
            t0 = min(t0, 11.2)
            self._corridor(d, sp, lt, t0 - 0.9, (tx_km, ty_km), ppk)
            if lt >= t0:
                self._hub(d, sp(tx_km, ty_km), lt - t0, ui["towns"][name], label_pos[name])

        self._legend(d, wx0, wy0 + wh, lt)
        # scale bar + north arrow
        bx1 = wx0 + ww - 26
        by = wy0 + wh - 40
        L = 5 * ppk
        d.rectangle((bx1 - L, by, bx1, by + 8), fill=rgba(C.WHITE, 0.9))
        d.rectangle((bx1 - L / 2, by, bx1, by + 8), fill=rgba(C.ASH, 0.9))
        d.text((bx1 - L / 2, by - 8), "5 KM", font=C.font("mono", 18), fill=rgba(C.WHITE, 0.9), anchor="mb")
        d.text((bx1, by + 26), ui["schematic"], font=C.font("mono", 14), fill=rgba(C.GRAY, 0.9), anchor="rm")
        nx, ny = wx0 + ww - 50, wy0 + 30
        d.polygon([(nx, ny), (nx - 13, ny + 34), (nx, ny + 26), (nx + 13, ny + 34)], fill=rgba(C.WHITE, 0.95))
        d.text((nx, ny + 52), "N", font=C.font("bold", 22), fill=rgba(C.WHITE, 0.95), anchor="mm")

    def _corridor(self, d, sp, lt, t_start, town, ppk):
        if lt < t_start:
            return
        prog = ease_in_out((lt - t_start) / 0.9)
        tx, ty = town
        dist = math.hypot(tx, ty)
        ux, uy = tx / dist, ty / dist
        a = (ux * 6.0, uy * 6.0)
        mid = ((a[0] + tx) / 2 - uy * dist * 0.08, (a[1] + ty) / 2 + ux * dist * 0.08)
        pts = []
        n = 40
        for i in range(int(n * prog) + 1):
            s = i / n
            bx = (1 - s) ** 2 * a[0] + 2 * (1 - s) * s * mid[0] + s * s * tx
            by = (1 - s) ** 2 * a[1] + 2 * (1 - s) * s * mid[1] + s * s * ty
            pts.append(sp(bx, by))
        if len(pts) < 2:
            return
        d.line(pts, fill=rgba((0, 0, 0), 0.55), width=12, joint="curve")
        # marching dashes along the path
        dash, gap = 20, 12
        arr = np.asarray(pts, dtype=np.float64)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(arr, axis=0).T))])
        total = cum[-1]
        s = -((lt * 70) % (dash + gap))
        while s < total:
            a0, a1 = max(0.0, s), min(total, s + dash)
            if a1 > a0:
                ss = np.linspace(a0, a1, 4)
                seg_pts = list(zip(np.interp(ss, cum, arr[:, 0]), np.interp(ss, cum, arr[:, 1])))
                d.line(seg_pts, fill=rgba(C.SULFUR, 1), width=6)
            s += dash + gap
        # arrow head
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        ang = math.atan2(y2 - y1, x2 - x1)
        L = 22
        d.polygon([(x2, y2), (x2 - L * math.cos(ang - 0.45), y2 - L * math.sin(ang - 0.45)),
                   (x2 - L * math.cos(ang + 0.45), y2 - L * math.sin(ang + 0.45))], fill=rgba(C.SULFUR, 1))

    def _hub(self, d, pos, age, name, where):
        x, y = pos
        k = ease_back(age / 0.4)
        r = 15 * k
        d.ellipse((x - r - 6, y - r - 6, x + r + 6, y + r + 6), fill=rgba(C.SULFUR, 0.35))
        d.ellipse((x - r, y - r, x + r, y + r), fill=rgba(C.WHITE, 1), outline=rgba(C.ASH, 1), width=3)
        d.ellipse((x - r * 0.4, y - r * 0.4, x + r * 0.4, y + r * 0.4), fill=rgba(C.ORANGE, 1))
        a = ease_out((age - 0.1) / 0.35)
        if a <= 0:
            return
        f1, f2 = C.font("bold", 26), C.font("mono", 16)
        w = max(f1.getlength(name), f2.getlength(self.ui["hub"])) + 24
        if where == "right":
            bx, by = x + 26, y - 30
        elif where == "left":
            bx, by = x - 26 - w, y - 8
        else:
            bx, by = x - 30, y + 26
        bx = min(bx, C.PANEL_X1 - 20 - w)
        d.rounded_rectangle((bx, by, bx + w, by + 60), radius=8, fill=rgba(C.ASH, 0.88 * a),
                            outline=rgba(C.SULFUR, a), width=2)
        d.text((bx + 12, by + 6), name, font=f1, fill=rgba(C.WHITE, a))
        d.text((bx + 12, by + 38), self.ui["hub"], font=f2, fill=rgba(C.SULFUR, a))

    def _legend(self, d, x0, ybot, lt):
        a = ease_out((lt - 2.4) / 0.5)
        if a <= 0:
            return
        f = C.font("mono", 18)
        items = self.ui["legend"]
        w = max(f.getlength(s) for s in items) + 76
        bx, by = x0 + 18, ybot - 18 - 112
        d.rounded_rectangle((bx, by, bx + w, by + 112), radius=10, fill=rgba(C.ASH, 0.85 * a),
                            outline=rgba(C.ASH_3, a), width=2)
        y = by + 22
        d.arc((bx + 14, y - 12, bx + 44, y + 18), 200, 340, fill=rgba(C.ORANGE, a), width=5)
        d.text((bx + 58, y), items[0], font=f, fill=rgba(C.WHITE, a), anchor="lm")
        y += 34
        for k in range(2):
            d.line([(bx + 14 + k * 16, y), (bx + 24 + k * 16, y)], fill=rgba(C.SULFUR, a), width=5)
        d.polygon([(bx + 46, y), (bx + 36, y - 7), (bx + 36, y + 7)], fill=rgba(C.SULFUR, a))
        d.text((bx + 58, y), items[1], font=f, fill=rgba(C.WHITE, a), anchor="lm")
        y += 34
        d.ellipse((bx + 20, y - 10, bx + 40, y + 10), fill=rgba(C.WHITE, a), outline=rgba(C.ASH, a), width=2)
        d.ellipse((bx + 26, y - 4, bx + 34, y + 4), fill=rgba(C.ORANGE, a))
        d.text((bx + 58, y), items[2], font=f, fill=rgba(C.WHITE, a), anchor="lm")

    # ======================================================= SCENE 3 ===
    def scene3(self, cv, d, lt, oy):
        cards = self.ui["cards"]
        ch, gap = 172, 14
        y0 = C.PANEL_TOP + 6 + oy
        act_times = [self.cue_lt("evac", 2, 0.3), self.cue_lt("masks", 2, 5.5),
                     self.cue_lt("lahar", 2, 9.0) - 1.2, 10.9]
        t_evac2 = self.cue_lt("evac2", 2, 2.6)
        active = max([k for k, ta in enumerate(act_times) if lt >= ta - 0.15] or [0])
        accents = [C.ORANGE, C.WHITE, C.SULFUR, C.ORANGE]
        for k, card in enumerate(cards):
            rev = 0.1 + 0.22 * k
            if lt < rev:
                continue
            a = ease_out((lt - rev) / 0.4)
            x0 = C.PANEL_X0 + (1 - a) * 160
            y = y0 + k * (ch + gap)
            on = k == active
            d.rounded_rectangle((x0, y, x0 + 1000, y + ch), radius=18, fill=rgba(C.ASH, (0.70 if self.has_broll else 0.86) * a),
                                outline=rgba(C.ORANGE if on else C.ASH_3, a), width=4 if on else 2)
            # icon block
            ib = (x0 + 14, y + 14, x0 + 134, y + ch - 14)
            if k == 2:
                tile = self.with_alpha(self.hazard_tile.crop((0, 0, 120, ch - 28)), a)
                cv.paste(tile, (int(ib[0]), int(ib[1])), tile)
            else:
                d.rounded_rectangle(ib, radius=12, fill=rgba(accents[k], 0.16 * a + (0.1 if on else 0)))
            self._icon(d, k, ((ib[0] + ib[2]) / 2, (ib[1] + ib[3]) / 2), a, lt)
            tx = x0 + 160
            vf_size = 64
            # value text with counters
            frac = ease_out((lt - rev - 0.15) / 1.3)
            if k == 0:
                first, second = [s.strip() for s in card["value"].split("→")]
                if lt < t_evac2:
                    val = count_fmt(first, frac)
                else:
                    f2 = ease_out((lt - t_evac2) / 0.8)
                    lo = int(re.sub(r"\D", "", first))
                    val = first + " → " + count_fmt(second, f2, start=lo)
            elif k == 1:
                val = count_fmt(card["value"], frac)
            else:
                val = card["value"]
            col = {0: C.WHITE, 1: C.WHITE, 2: C.SULFUR, 3: C.ORANGE}[k]
            vf = C.fit_font("display", card["value"] if k else card["value"], 690 if k == 3 else 820, vf_size)
            d.text((tx, y + 18), val, font=vf, fill=rgba(col, a))
            d.text((tx, y + 98), card["label"], font=C.fit_font("mono", card["label"], 820, 26),
                   fill=rgba(C.WHITE, a))
            d.text((tx, y + 134), card["sub"], font=C.fit_font("mono", card["sub"], 820, 19),
                   fill=rgba(C.GRAY, a))
            if k == 3:     # PHIVOLCS 0-5 alert meter, level 3 lit
                mx = x0 + 820
                for lvl in range(1, 6):
                    bx = mx + (lvl - 1) * 34
                    hgt = 22 + lvl * 9
                    lit = lvl <= 3
                    col2 = C.ORANGE if lit else C.ASH_3
                    alpha = a * (0.55 + 0.45 * math.sin(lt * 6) if lvl == 3 else a)
                    d.rectangle((bx, y + 86 - hgt, bx + 24, y + 86), fill=rgba(col2, alpha if lit else a))
                    d.text((bx + 12, y + 92), str(lvl), font=C.font("mono", 14),
                           fill=rgba(C.GRAY, a), anchor="mt")

    def _icon(self, d, k, c, a, lt):
        x, y = c
        if k == 0:      # people
            for dx, s in ((-26, 0.8), (26, 0.8), (0, 1.0)):
                r = 13 * s
                d.ellipse((x + dx - r, y - 30 * s - r, x + dx + r, y - 30 * s + r), fill=rgba(C.WHITE, a))
                d.rounded_rectangle((x + dx - 20 * s, y - 12 * s, x + dx + 20 * s, y + 30 * s),
                                    radius=int(14 * s), fill=rgba(C.WHITE, a))
            d.polygon([(x - 46, y + 44), (x + 30, y + 44), (x + 30, y + 54), (x + 50, y + 40),
                       (x + 30, y + 26), (x + 30, y + 36), (x - 46, y + 36)], fill=rgba(C.ORANGE, a))
        elif k == 1:    # protective mask
            d.rounded_rectangle((x - 38, y - 24, x + 38, y + 26), radius=20, fill=rgba(C.WHITE, a))
            for yy in (-8, 4, 16):
                d.line([(x - 26, y + yy), (x + 26, y + yy)], fill=rgba(C.GRAY_DIM, a), width=3)
            d.arc((x - 54, y - 30, x - 26, y + 10), 90, 270, fill=rgba(C.WHITE, a), width=4)
            d.arc((x + 26, y - 30, x + 54, y + 10), 270, 90, fill=rgba(C.WHITE, a), width=4)
        elif k == 2:    # hazard triangle
            blink = 1.0 if (lt % 0.9) < 0.6 else 0.55
            d.polygon([(x, y - 44), (x - 46, y + 36), (x + 46, y + 36)], fill=rgba(C.ASH, a),
                      outline=rgba(C.SULFUR, a * blink))
            d.text((x, y + 6), "!", font=C.font("display", 54), fill=rgba(C.SULFUR, a * blink), anchor="mm")
        else:           # volcano with plume
            d.polygon([(x - 50, y + 40), (x - 10, y - 18), (x + 10, y - 18), (x + 50, y + 40)],
                      fill=rgba(C.WHITE, a))
            for i, (dx, dy, r) in enumerate(((0, -30, 12), (-10, -48, 15), (12, -58, 16))):
                d.ellipse((x + dx - r, y + dy - r, x + dx + r, y + dy + r), fill=rgba(C.ORANGE, a))

    # ======================================================= SCENE 4 ===
    def scene4(self, cv, d, lt, oy):
        ui = self.ui
        top = C.PANEL_TOP + oy
        box = (C.PANEL_X0, top, C.PANEL_X1, top + 600)
        self.panel(d, box, None, accent=C.SULFUR)
        blink = (lt % 1.0) < 0.6
        d.ellipse((72, top + 32, 94, top + 54), fill=rgba(C.RED, 1 if blink else 0.3))
        d.text((110, top + 43), ui["s4_title"], font=C.fit_font("display", ui["s4_title"], 640, 36),
               fill=rgba(C.WHITE, 1), anchor="lm")
        d.text((C.PANEL_X1 - 30, top + 43), "PHIVOLCS / APSEMO", font=C.font("mono", 18),
               fill=rgba(C.GRAY, 1), anchor="rm")
        d.line([(70, top + 80), (C.PANEL_X1 - 30, top + 80)], fill=rgba(C.ASH_3, 1), width=2)
        colors = {"orange": C.ORANGE, "red": C.RED, "sulfur": C.SULFUR}
        lf = C.font("mono", 24)
        for k, (label, value, ckey) in enumerate(ui["s4_rows"]):
            t0 = 0.3 + 0.55 * k
            if lt < t0:
                continue
            y = top + 92 + k * 82
            a = ease_out((lt - t0) / 0.25)
            if k % 2 == 0:
                d.rectangle((62, y, C.PANEL_X1 - 22, y + 74), fill=rgba(C.WHITE, 0.035 * a))
            d.text((78, y + 37), label, font=lf, fill=rgba(C.GRAY, a), anchor="lm")
            n = int(clamp((lt - t0) * 38 / max(1, len(value))) * len(value))
            typed = value[:n]
            vf = C.fit_font("bold", value, 560, 32)
            col = colors[ckey]
            d.text((300, y + 37), typed, font=vf, fill=rgba(col, a), anchor="lm")
            if n < len(value) and (lt * 8) % 2 < 1:
                cx = 300 + vf.getlength(typed) + 4
                d.rectangle((cx, y + 20, cx + 14, y + 54), fill=rgba(col, 0.9))
            led = 0.5 + 0.5 * math.sin(lt * 5 + k)
            d.ellipse((C.PANEL_X1 - 64, y + 25, C.PANEL_X1 - 40, y + 49), fill=rgba(col, 0.35 + 0.65 * led))

        # call to action
        t_cta = self.cue_lt("follow", 3, 7.6) - 0.3
        cy0 = top + 628
        if lt < t_cta:
            a = 0.6 + 0.4 * math.sin(lt * 4)
            msg = "● LIVE MONITORING • MAYON VOLCANO" if self.lang == "en" else "● MONITORAMENTO AO VIVO • VULCÃO MAYON"
            d.text((C.W // 2, cy0 + 60), msg, font=C.font("mono", 24), fill=rgba(C.GRAY, a), anchor="mm")
            return
        age = lt - t_cta
        k = ease_back(age / 0.45)
        pulse = 1 + 0.02 * math.sin(age * 5)
        spr = self._cta_sprite()
        s = max(0.05, k * pulse)
        im = spr.resize((int(spr.width * s), int(spr.height * s)), Image.BILINEAR)
        cv.paste(im, (C.W // 2 - im.width // 2, cy0 + 60 - im.height // 2), im)

    def _cta_sprite(self):
        if "cta" in self._sprites:
            return self._sprites["cta"]
        w, h = 960, 150
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w - 1, 92), radius=18, fill=rgba(C.ORANGE, 1))
        d.rectangle((0, 70, w - 1, 92), fill=rgba(C.ORANGE, 1))
        d.rounded_rectangle((0, 86, w - 1, h - 1), radius=18, fill=rgba((12, 12, 14), 1),
                            outline=rgba(C.ORANGE, 1), width=3)
        f1 = C.fit_font("display", self.ui["cta_1"], w - 80, 58)
        d.text((w // 2, 46), self.ui["cta_1"], font=f1, fill=rgba(C.ASH, 1), anchor="mm")
        f2 = C.fit_font("mono", self.ui["cta_2"], w - 80, 30)
        d.text((w // 2, 119), self.ui["cta_2"], font=f2, fill=rgba(C.WHITE, 1), anchor="mm")
        self._sprites["cta"] = img
        return img
