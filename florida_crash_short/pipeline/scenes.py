"""The four broadcast scenes. Each scene draws a transparent full-frame RGBA
layer for a given local time (seconds since the scene started)."""
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from . import config as C  # noqa: E402
from . import geo  # noqa: E402
from .graphics import (clamp, draw_text, ease_in_out, ease_out, fit_font, font,  # noqa: E402
                       lerp_color, panel, prog, pulse, rgba, section_title, tag,
                       text_w, wrap)

F = C.FACTS


def _mpl_font(name="Inter-Bold.otf"):
    return font_manager.FontProperties(fname=str(C.FONTS / name))


def _hex(c):
    return "#%02x%02x%02x" % tuple(c[:3])


def _fig_to_image(fig):
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba()).copy()
    plt.close(fig)
    return Image.fromarray(buf, "RGBA")


def _word_time(words, scene_id, needle, default):
    """Local time (s since scene start) when a narrated word begins."""
    sc = next(s for s in C.SCENES if s["id"] == scene_id)
    for w in words:
        if w["scene"] == scene_id and needle.lower() in w["text"].lower():
            return w["start"] - sc["start"]
    return default


class Scene:
    def __init__(self, words, photo_mode=False):
        self.words = words
        self.photo = photo_mode
        self.panel_alpha = 196 if photo_mode else 236

    def layer(self):
        return Image.new("RGBA", (C.W, C.H), (0, 0, 0, 0))


# =========================================================================== #
# Scene 1 - flight path map
# =========================================================================== #
class MapScene(Scene):
    BOX = (C.MARGIN - 8, 510, C.W - C.MARGIN + 8, 1110)
    HI = 2  # basemap supersampling for crisp zooms

    def __init__(self, words, photo_mode=False):
        super().__init__(words, photo_mode)
        x0, y0, x1, y1 = self.BOX
        self.mw, self.mh = x1 - x0, y1 - y0
        lat_c = 27.0
        self.lon0, self.lon1 = -99.8, -74.6
        span_lat = (self.lon1 - self.lon0) * math.cos(math.radians(lat_c)) * self.mh / self.mw
        self.lat0 = 27.45 - span_lat / 2
        self.lat1 = 27.45 + span_lat / 2
        self.base = self._render_basemap()
        if photo_mode:
            a = self.base.getchannel("A").point(lambda v: int(v * 0.86))
            self.base.putalpha(a)
        self.mask = Image.new("L", (self.mw, self.mh), 0)
        ImageDraw.Draw(self.mask).rounded_rectangle((0, 0, self.mw - 1, self.mh - 1), 16, fill=255)
        aus, crash = C.GEO["AUS"], C.GEO["CRASH"]
        ctrl = ((aus[0] + crash[0]) / 2, (aus[1] + crash[1]) / 2 + 1.3)
        u = np.linspace(0, 1, 240)[:, None]
        self.track = ((1 - u) ** 2 * np.array(aus) + 2 * (1 - u) * u * np.array(ctrl) + u ** 2 * np.array(crash))
        self.t_crash = 6.0
        self.t_fly = (0.9, self.t_crash)

    # ---- static basemap -------------------------------------------------- #
    def _render_basemap(self):
        region = geo.load_region()
        w, h = self.mw * self.HI, self.mh * self.HI
        fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
        ax = fig.add_axes([0, 0, 1, 1])
        fig.patch.set_facecolor(_hex(C.OCEAN))
        ax.set_facecolor(_hex(C.OCEAN))
        ax.set_xlim(self.lon0, self.lon1)
        ax.set_ylim(self.lat0, self.lat1)
        ax.axis("off")
        for lon in range(-100, -70, 5):
            ax.axvline(lon, color=_hex(C.NAVY_MID), lw=1.2, alpha=0.6, zorder=0)
        for lat in range(15, 40, 5):
            ax.axhline(lat, color=_hex(C.NAVY_MID), lw=1.2, alpha=0.6, zorder=0)
        for ring in region["land"]:
            xs, ys = zip(*ring)
            ax.fill(xs, ys, color=_hex(C.LAND), zorder=1)
            ax.plot(xs, ys, color=_hex(C.LAND_EDGE), lw=2.2, zorder=3)
        for ring in region["states"]:
            xs, ys = zip(*ring)
            ax.plot(xs, ys, color=_hex(C.NAVY_LINE), lw=1.3, alpha=0.9, zorder=2)
        fp = _mpl_font("Inter-SemiBold.otf")
        labels = [("TEXAS", -99.0, 31.6), ("LOUISIANA", -92.6, 31.2), ("MISSISSIPPI", -89.7, 32.7),
                  ("ALABAMA", -86.8, 32.6), ("GEORGIA", -83.4, 32.4), ("FLORIDA", -81.7, 28.3),
                  ("MEXICO", -98.9, 23.6), ("CUBA", -79.6, 21.95), ("BAHAMAS", -76.2, 24.0)]
        for name, lon, lat in labels:
            if self.lon0 < lon < self.lon1 and self.lat0 < lat < self.lat1:
                ax.text(lon, lat, name, fontproperties=fp, fontsize=30, color=_hex(C.MUTED),
                        alpha=0.85, ha="center", va="center", zorder=4)
        return _fig_to_image(fig)

    # ---- geometry -------------------------------------------------------- #
    def _view(self, t):
        z = 1 + 1.35 * ease_in_out(prog(t, self.t_crash + 0.35, 3.0))
        W, H = self.base.size
        tx, ty = self._hi((C.GEO["CRASH"][0] + 1.4, C.GEO["CRASH"][1] - 0.2))
        k = ease_in_out(prog(t, self.t_crash + 0.35, 3.0))
        cx, cy = W / 2 + (tx - W / 2) * k, H / 2 + (ty - H / 2) * k
        cw, ch = W / z, H / z
        cx = clamp(cx, cw / 2, W - cw / 2)
        cy = clamp(cy, ch / 2, H - ch / 2)
        return (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)

    def _hi(self, p):
        lon, lat = p
        W, H = self.base.size
        return ((lon - self.lon0) / (self.lon1 - self.lon0) * W,
                (self.lat1 - lat) / (self.lat1 - self.lat0) * H)

    def _px(self, p, view):
        hx, hy = self._hi(p)
        sx = self.mw / (view[2] - view[0])
        return ((hx - view[0]) * sx, (hy - view[1]) * sx)

    # ---- frame ----------------------------------------------------------- #
    def draw(self, t):
        L = self.layer()
        # opens almost fully formed: the first frame doubles as the hook/thumbnail
        section_title(L, t + 0.4, "FLIGHT PATH", "AUSTIN → PALM BEACH CO.")
        a_in = ease_out(prog(t, -0.25, 0.45))
        if a_in <= 0:
            return L
        view = self._view(t)
        m = self.base.resize((self.mw, self.mh), Image.BILINEAR, box=view)
        ov = Image.new("RGBA", (self.mw, self.mh), (0, 0, 0, 0))
        d = ImageDraw.Draw(ov)
        px = lambda p: self._px(p, view)

        # planned remainder of the route (crash site -> North Eleuthera)
        if t > self.t_crash + 0.4:
            k = ease_out(prog(t, self.t_crash + 0.4, 1.2))
            p0, p1 = np.array(px(C.GEO["CRASH"])), np.array(px(C.GEO["ELH"]))
            n = 22
            for i in range(0, n, 2):
                s0, s1 = i / n, min((i + 1) / n, k)
                if s0 >= k:
                    break
                d.line([tuple(p0 + (p1 - p0) * s0), tuple(p0 + (p1 - p0) * s1)],
                       fill=rgba(C.OFFWHITE, 170), width=4)

        # flown track with glow
        fp = ease_in_out(prog(t, *(self.t_fly[0], self.t_fly[1] - self.t_fly[0])))
        n = max(2, int(fp * (len(self.track) - 1)) + 1)
        pts = [px(p) for p in self.track[:n]]
        if fp > 0:
            for wdt, al, col in [(18, 40, C.CYAN), (10, 90, C.CYAN), (5, 255, C.WHITE)]:
                d.line(pts, fill=rgba(col, al), width=wdt, joint="curve")

        # markers
        self._marker(d, px(C.GEO["AUS"]), C.WHITE, ease_out(prog(t, 0.7, 0.4)))
        self._label(ov, px(C.GEO["AUS"]), "AUSTIN, TX", "DEPARTED  AUS", "below",
                    ease_out(prog(t, 0.8, 0.4)))
        elh_a = ease_out(prog(t, self.t_crash + 1.0, 0.5))
        self._marker(d, px(C.GEO["ELH"]), C.MUTED, elh_a, hollow=True)
        self._label(ov, px(C.GEO["ELH"]), "N. ELEUTHERA", "PLANNED  ELH", "below", elh_a)

        # plane icon while in flight
        if 0 < fp < 1:
            p_a, p_b = pts[-1], pts[-2] if len(pts) > 1 else pts[-1]
            ang = math.atan2(p_a[1] - p_b[1], p_a[0] - p_b[0])
            self._plane(d, p_a, ang)

        # crash site
        if t >= self.t_crash:
            c = px(C.GEO["CRASH"])
            dt = t - self.t_crash
            flash = clamp(1 - dt / 0.5)
            if flash > 0:
                r = 30 + 90 * dt
                d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), fill=rgba(C.AMBER, 120 * flash))
            for k in range(3):
                ph = (dt * 0.75 + k / 3) % 1
                r = 12 + 54 * ph
                d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r), outline=rgba(C.RED, 255 * (1 - ph)), width=4)
            d.ellipse((c[0] - 11, c[1] - 11, c[0] + 11, c[1] + 11), fill=rgba(C.RED), outline=rgba(C.WHITE), width=3)
            self._callout(ov, c, ease_out(prog(t, self.t_crash + 0.6, 0.5)))

        m.alpha_composite(ov)
        frame_m = Image.new("RGBA", (self.mw, self.mh), (0, 0, 0, 0))
        frame_m.paste(m, (0, 0), self.mask)
        if a_in < 1:
            frame_m.putalpha(frame_m.getchannel("A").point(lambda v: int(v * a_in)))
        x0, y0, x1, y1 = self.BOX
        panel(L, self.BOX, alpha=int(self.panel_alpha * a_in), accent=None)
        L.alpha_composite(frame_m, (x0, y0))
        ImageDraw.Draw(L).rounded_rectangle(self.BOX, 16, outline=rgba(C.NAVY_LINE, 230 * a_in), width=3)
        self._legend(L, t)
        return L

    def _marker(self, d, p, col, a, hollow=False):
        if a <= 0:
            return
        r = 11 * a
        if hollow:
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), outline=rgba(col, 255 * a), width=4,
                      fill=rgba(C.NAVY_DEEP, 200 * a))
        else:
            d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=rgba(col, 255 * a),
                      outline=rgba(C.NAVY_DEEP, 255 * a), width=3)

    def _label(self, ov, p, title, sub, where, a):
        if a <= 0:
            return
        d = ImageDraw.Draw(ov)
        ft, fs = font("xbold", 26), font("bold", 18)
        w = max(text_w(title, ft), text_w(sub, fs, 2)) + 28
        x = clamp(p[0] - w / 2, 8, self.mw - w - 8)
        y = p[1] + 22 if where == "below" else p[1] - 92
        y = clamp(y, 8, self.mh - 76)
        d.rounded_rectangle((x, y, x + w, y + 68), 8, fill=rgba(C.NAVY_DEEP, 215 * a),
                            outline=rgba(C.NAVY_LINE, 255 * a), width=2)
        draw_text(d, (x + 14, y + 32), title, ft, C.WHITE, anchor="ls", alpha=255 * a)
        draw_text(d, (x + 14, y + 56), sub, fs, C.MUTED, anchor="ls", tracking=2, alpha=255 * a)

    def _callout(self, ov, c, a):
        if a <= 0:
            return
        d = ImageDraw.Draw(ov)
        w, h = 400, 150
        x = clamp(c[0] - w - 60, 10, self.mw - w - 10)
        y = clamp(c[1] - h - 50, 10, self.mh - h - 10)
        x += 30 * (1 - a)
        d.line((c[0], c[1], x + w, y + h), fill=rgba(C.WHITE, 220 * a), width=3)
        d.rounded_rectangle((x, y, x + w, y + h), 10, fill=rgba(C.NAVY_DEEP, 235 * a),
                            outline=rgba(C.RED, 255 * a), width=3)
        tag(ov, (x + 16, y + 14), "CRASH SITE", size=22, pad=(12, 6), alpha=255 * a)
        draw_text(d, (x + 16, y + 92), "GREENACRES, FL", font("black", 38), anchor="ls", alpha=255 * a)
        draw_text(d, (x + 16, y + 128), "PALM BEACH COUNTY", font("bold", 22), C.AMBER,
                  anchor="ls", tracking=3, alpha=255 * a)

    def _plane(self, d, p, ang, s=1.5):
        shape = [(24, 0), (6, -3), (-2, -17), (-7, -17), (-1, -3), (-14, -3), (-19, -9), (-22, -9),
                 (-18, 0), (-22, 9), (-19, 9), (-14, 3), (-1, 3), (-7, 17), (-2, 17), (6, 3)]
        ca, sa = math.cos(ang), math.sin(ang)
        poly = [(p[0] + s * (x * ca - y * sa), p[1] + s * (x * sa + y * ca)) for x, y in shape]
        d.polygon(poly, fill=rgba(C.WHITE), outline=rgba(C.NAVY_DEEP))

    def _legend(self, L, t):
        a = ease_out(prog(t, 1.0, 0.5))
        if a <= 0:
            return
        d = ImageDraw.Draw(L)
        y = 1146
        f = font("bold", 24)
        x = C.MARGIN
        d.ellipse((x, y - 9, x + 18, y + 9), fill=rgba(C.WHITE, 255 * a))
        x += 30
        x += draw_text(d, (x, y + 1), "DEPARTED", f, C.OFFWHITE, anchor="lm", alpha=255 * a, tracking=1) + 34
        d.ellipse((x, y - 9, x + 18, y + 9), fill=rgba(C.RED, 255 * a))
        x += 30
        x += draw_text(d, (x, y + 1), "CRASH", f, C.OFFWHITE, anchor="lm", alpha=255 * a, tracking=1) + 34
        for i in range(3):
            d.line((x + i * 12, y, x + i * 12 + 7, y), fill=rgba(C.OFFWHITE, 255 * a), width=4)
        x += 46
        draw_text(d, (x, y + 1), "PLANNED", f, C.OFFWHITE, anchor="lm", alpha=255 * a, tracking=1)
        draw_text(d, (C.W - C.MARGIN, y + 1), "ROUTE ILLUSTRATIVE", font("semi", 20), C.MUTED,
                  anchor="rm", tracking=2, alpha=255 * a)


# =========================================================================== #
# Scene 2 - altitude & descent telemetry
# =========================================================================== #
def altitude_profile(s):
    """Reported envelope: 35,250 ft -> 8,750 ft over 60 s, dive rate within the
    reported 10,000-30,000 ft/min. Rate ramps 10k -> 30k fpm over 21 s, then
    holds 30k; integrates to exactly 26,500 ft lost."""
    s = np.clip(s, 0, 60)
    ramp = np.minimum(s, 21.0)
    drop = (10_000 * ramp + 20_000 * ramp ** 2 / (2 * 21.0)) / 60
    drop = drop + np.maximum(s - 21.0, 0) * 30_000 / 60
    rate = np.where(s < 21, 10_000 + 20_000 * s / 21, 30_000)
    return F["telemetry_start_ft"] - drop, rate


class TelemetryScene(Scene):
    GBOX = (C.MARGIN - 8, 712, C.W - C.MARGIN + 8, 1140)

    def __init__(self, words, photo_mode=False):
        super().__init__(words, photo_mode)
        self.t_dive = _word_time(words, "telemetry", "entered", 6.0) - 0.1
        self.t_mayday = _word_time(words, "telemetry", "mayday", 11.0) - 0.1
        self.dive_len = 6.6  # seconds of video to play the 60 s profile
        x0, y0, x1, y1 = self.GBOX
        self.gw, self.gh = x1 - x0, y1 - y0
        self.graph = self._render_graph()

    def _render_graph(self):
        fig = plt.figure(figsize=(self.gw / 100, self.gh / 100), dpi=100)
        fig.patch.set_alpha(0)
        ax = fig.add_axes([0.13, 0.13, 0.84, 0.80])
        ax.set_facecolor("none")
        ax.set_xlim(0, 60)
        ax.set_ylim(0, 40_000)
        fp = _mpl_font("Inter-SemiBold.otf")
        fpm = font_manager.FontProperties(fname=str(C.FONTS / "JetBrainsMono-Bold.ttf"))
        ax.set_yticks(range(0, 40_001, 10_000))
        ax.set_yticklabels([f"{v // 1000}K" if v else "0" for v in range(0, 40_001, 10_000)],
                           fontproperties=fpm, fontsize=17, color=_hex(C.MUTED))
        ax.set_xticks(range(0, 61, 10))
        ax.set_xticklabels([f"{v}s" for v in range(0, 61, 10)], fontproperties=fpm, fontsize=17,
                           color=_hex(C.MUTED))
        ax.tick_params(length=0, pad=8)
        ax.grid(True, color=_hex(C.NAVY_LINE), lw=1, alpha=0.55)
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.axhline(35_000, color=_hex(C.AMBER), lw=1.6, ls=(0, (5, 4)), alpha=0.85)
        ax.text(59.3, 36_200, "35,000 FT  CONDITIONS REPORTED", fontproperties=fp, fontsize=14,
                color=_hex(C.AMBER), ha="right", va="bottom")
        ax.set_ylabel("ALTITUDE (FT)", fontproperties=fp, fontsize=15, color=_hex(C.MUTED), labelpad=10)
        ax.set_xlabel("SECONDS INTO DIVE", fontproperties=fp, fontsize=15, color=_hex(C.MUTED), labelpad=6)
        fig.canvas.draw()
        # data -> pixel mapping (Pillow coords, origin top-left of the graph box)
        (px0, py0), (px1, py1) = ax.transData.transform([(0, 0), (60, 40_000)])
        self._map = (px0, self.gh - py0, px1, self.gh - py1)
        return _fig_to_image(fig)

    def _gp(self, s, alt):
        px0, py0, px1, py1 = self._map
        return (px0 + (px1 - px0) * s / 60, py0 + (py1 - py0) * alt / 40_000)

    def draw(self, t):
        L = self.layer()
        section_title(L, t, "TELEMETRY", "ALTITUDE & DESCENT")
        d = ImageDraw.Draw(L)
        s_now = 60 * ease_in_out(prog(t, self.t_dive, self.dive_len)) if t >= self.t_dive else 0.0
        alt, rate = altitude_profile(np.array([s_now]))
        alt, rate = float(alt[0]), float(rate[0])
        diving = t >= self.t_dive

        # --- readouts -------------------------------------------------------
        boxes = [("ALTITUDE", f"{int(round(alt / 10) * 10):,}", "FT", C.WHITE),
                 ("VERTICAL SPEED", f"-{int(round(rate / 100) * 100):,}" if diving else "LEVEL", "FT/MIN" if diving else "",
                  C.RED if diving else C.WHITE),
                 ("DIVE ELAPSED", f"T+{int(s_now):02d}", "SEC", C.WHITE)]
        bw, gap, by = (C.W - 2 * C.MARGIN - 2 * 16) / 3, 16, 508
        for i, (lab, val, unit, col) in enumerate(boxes):
            a = ease_out(prog(t, 0.25 + 0.1 * i, 0.4))
            if a <= 0:
                continue
            x = C.MARGIN + i * (bw + gap)
            panel(L, (x, by + 20 * (1 - a), x + bw, by + 122 + 20 * (1 - a)), alpha=int(self.panel_alpha * a),
                  accent=C.RED if (i == 1 and diving) else C.NAVY_LINE)
            draw_text(d, (x + 18, by + 40), lab, font("bold", 19), C.MUTED, tracking=2, alpha=255 * a)
            fv = fit_font(val, "monox", 46, bw - 36)
            draw_text(d, (x + 18, by + 92), val, fv, col, alpha=255 * a)
            draw_text(d, (x + 18, by + 114), unit, font("bold", 16), C.MUTED, tracking=2, alpha=255 * a)

        # --- reported conditions chips ---------------------------------------
        cx, cy = C.MARGIN, 648
        for i, cond in enumerate(F["conditions"]):
            a = ease_out(prog(t, _word_time(self.words, "telemetry", cond.lower()[:6], 1 + i) - 0.15, 0.3))
            if a <= 0:
                continue
            w, _ = tag(L, (cx, cy), cond, bg=C.AMBER, fg=C.NAVY_DEEP, size=24, pad=(14, 8), alpha=255 * a)
            cx += w + 12
        draw_text(d, (C.W - C.MARGIN, cy + 30), "@ 35,000 FT", font("monox", 26), C.AMBER, anchor="rm",
                  alpha=255 * ease_out(prog(t, 0.6, 0.4)))

        # --- graph ----------------------------------------------------------
        ga = ease_out(prog(t, 0.35, 0.5))
        x0, y0, x1, y1 = self.GBOX
        panel(L, self.GBOX, alpha=int(self.panel_alpha * ga), accent=None)
        if ga > 0:
            g = self.graph if ga >= 1 else self.graph.copy()
            if ga < 1:
                g.putalpha(g.getchannel("A").point(lambda v: int(v * ga)))
            L.alpha_composite(g, (x0, y0))
        ov = Image.new("RGBA", (self.gw, self.gh), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)
        ss = np.linspace(0, s_now, max(2, int(s_now * 4) + 2))
        alts, _ = altitude_profile(ss)
        pts = [self._gp(s, a) for s, a in zip(ss, alts)]
        if ga > 0.5:
            # area fill under the curve
            if s_now > 0.3:
                poly = pts + [self._gp(s_now, 0), self._gp(0, 0)]
                od.polygon(poly, fill=rgba(C.RED, 46))
            for wdt, al, col in [(16, 45, C.RED), (9, 110, C.RED), (5, 255, (255, 94, 94))]:
                od.line(pts, fill=rgba(col, al), width=wdt, joint="curve")
            hx, hy = pts[-1]
            r = 10 + 5 * pulse(t, 2.0)
            od.ellipse((hx - r, hy - r, hx + r, hy + r), outline=rgba(C.WHITE, 200), width=3)
            od.ellipse((hx - 7, hy - 7, hx + 7, hy + 7), fill=rgba(C.WHITE))
            # start + end labels
            sx, sy = self._gp(0, F["telemetry_start_ft"])
            draw_text(od, (sx + 16, sy + 34), "35,250 FT", font("monox", 24), C.WHITE, anchor="ls")
            if s_now >= 59.5:
                ea = ease_out(prog(t, self.t_dive + self.dive_len, 0.4))
                ex, ey = self._gp(60, F["telemetry_end_ft"])
                od.rounded_rectangle((ex - 182, ey - 76, ex - 14, ey - 26), 8, fill=rgba(C.RED, 255 * ea))
                draw_text(od, (ex - 98, ey - 50), "8,750 FT", font("monox", 28), C.WHITE, anchor="mm", alpha=255 * ea)
        L.alpha_composite(ov, (x0, y0))

        # --- MAYDAY banner (triggered by the narration) ------------------------
        if t >= self.t_mayday:
            dt = t - self.t_mayday
            a = ease_out(prog(dt, 0, 0.18))
            flash = 1.0 if dt > 1.8 else (0.55 + 0.45 * (math.sin(dt * 2 * math.pi * 3) > 0))
            bx1, by0 = x1 - 26, y0 + 96
            bx0, by1 = bx1 - 452, by0 + 96
            d.rounded_rectangle((bx0, by0, bx1, by1), 12, fill=rgba(lerp_color(C.RED_DARK, C.RED, flash), 245 * a),
                                outline=rgba(C.WHITE, 230 * a), width=3)
            # radio waves icon
            ix, iy = bx0 + 50, (by0 + by1) / 2
            d.ellipse((ix - 8, iy - 8, ix + 8, iy + 8), fill=rgba(C.WHITE, 255 * a))
            for k, r in enumerate((20, 32)):
                d.arc((ix - r, iy - r, ix + r, iy + r), -50, 50, fill=rgba(C.WHITE, 255 * a), width=4)
                d.arc((ix - r, iy - r, ix + r, iy + r), 130, 230, fill=rgba(C.WHITE, 255 * a), width=4)
            draw_text(d, (bx0 + 96, by0 + 50), "MAYDAY", font("black", 46), anchor="ls", alpha=255 * a, tracking=2)
            draw_text(d, (bx0 + 98, by0 + 80), "EMERGENCY DECLARED BY PILOT", font("bold", 17), C.OFFWHITE,
                      anchor="ls", tracking=1, alpha=255 * a)

        draw_text(d, (C.MARGIN, 1172), "Illustrative profile built from reported figures: 35,250 → 8,750 ft in 60 s; "
                  "dive 10,000–30,000 ft/min.", fit_font("x" * 92, "medium", 20, C.W - 2 * C.MARGIN),
                  C.MUTED, alpha=230 * ga)
        return L


# =========================================================================== #
# Scene 3 - incident summary card
# =========================================================================== #
class SummaryScene(Scene):
    TW, TH = (C.W - 2 * C.MARGIN - 18) / 2, 286

    def __init__(self, words, photo_mode=False):
        super().__init__(words, photo_mode)
        self.tiles = [
            {"label": "AIRCRAFT", "big": "LEARJET 60", "col": C.WHITE, "size": 74,
             "sub": f"Private jet · Registration {F['registration']}", "cue": None},
            {"label": "FATALITIES ON BOARD", "big": str(F["fatalities"]), "col": C.RED, "size": 150,
             "sub": f"Confirmed by U.S. Transportation Secretary Sean Duffy", "cue": "nine"},
            {"label": "GROUND INJURIES REPORTED", "big": str(F["ground_injuries"]), "col": C.WHITE, "size": 150,
             "sub": f"No immediate reports — {F['ground_injuries_source']}", "cue": "ground"},
            {"label": "RESIDENTS EVACUATED", "big": str(F["evacuated"]), "col": C.AMBER, "size": 150,
             "sub": "About 600 nearby residents", "count": True, "cue": None},
        ]
        for tl in self.tiles:
            tl["t_cue"] = _word_time(words, "summary", tl["cue"], 99) if tl["cue"] else 99

    def draw(self, t):
        L = self.layer()
        section_title(L, t, "VERIFIED", "INCIDENT SUMMARY")
        d = ImageDraw.Draw(L)
        for i, tl in enumerate(self.tiles):
            a = ease_out(prog(t, 0.25 + 0.16 * i, 0.45))
            if a <= 0:
                continue
            col_i, row_i = i % 2, i // 2
            x = C.MARGIN + col_i * (self.TW + 18)
            y = 508 + row_i * (self.TH + 18) + 40 * (1 - a)
            hot = t >= tl["t_cue"]
            panel(L, (x, y, x + self.TW, y + self.TH), alpha=int(self.panel_alpha * a),
                  accent=tl["col"] if tl["col"] != C.WHITE else C.NAVY_LINE,
                  outline=C.RED if hot and pulse(t, 2) > 0.3 and t - tl["t_cue"] < 1.5 else C.NAVY_LINE)
            draw_text(d, (x + 24, y + 48), tl["label"], fit_font(tl["label"], "xbold", 22, self.TW - 48, 2),
                      C.MUTED, tracking=2, alpha=255 * a)
            big = tl["big"]
            if tl.get("count"):
                k = ease_out(prog(t, 0.25 + 0.16 * i, 1.4))
                big = f"{int(round(F['evacuated'] * k)):,}"
                if k >= 1:
                    big = "~600"
            fb = fit_font(big, "black", tl["size"], self.TW - 48)
            draw_text(d, (x + 22, y + 196), big, fb, tl["col"], alpha=255 * a, shadow=(0, 4, (0, 0, 0, 140)))
            fs = font("medium", 22)
            for li, line in enumerate(wrap(tl["sub"], fs, self.TW - 48)[:2]):
                draw_text(d, (x + 24, y + 234 + li * 28), line, fs, C.OFFWHITE, alpha=235 * a)

        a = ease_out(prog(t, 1.0, 0.5))
        if a > 0:
            y = 1120
            panel(L, (C.MARGIN, y, C.W - C.MARGIN, y + 66), alpha=int(self.panel_alpha * a), accent=None)
            f = font("bold", 24)
            draw_text(d, (C.MARGIN + 22, y + 34), f"{F['date_short']}  ·  {F['time']}", f, C.OFFWHITE,
                      anchor="lm", alpha=255 * a, tracking=1)
            draw_text(d, (C.W - C.MARGIN - 22, y + 34), "AUS → ELH", font("monox", 26), C.AMBER,
                      anchor="rm", alpha=255 * a)
        return L


# =========================================================================== #
# Scene 4 - investigation status + outro
# =========================================================================== #
class InvestigationScene(Scene):
    AGENCIES = [("FAA", "Federal Aviation Administration"),
                ("NTSB", "National Transportation Safety Board")]

    def __init__(self, words, photo_mode=False):
        super().__init__(words, photo_mode)
        self.t_outro = 3.0

    def draw(self, t):
        L = self.layer()
        section_title(L, t, "INVESTIGATION", "FAA & NTSB ON THE CASE")
        d = ImageDraw.Draw(L)
        x0, x1 = C.MARGIN, C.W - C.MARGIN
        for i, (abbr, name) in enumerate(self.AGENCIES):
            a = ease_out(prog(t, 0.25 + 0.15 * i, 0.45))
            if a <= 0:
                continue
            y = 508 + i * 126
            xo = -50 * (1 - a)
            panel(L, (x0 + xo, y, x1 + xo, y + 112), alpha=int(self.panel_alpha * a), accent=None)
            d.rounded_rectangle((x0 + xo + 14, y + 14, x0 + xo + 174, y + 98), 10, fill=rgba(C.NAVY_MID, 255 * a))
            draw_text(d, (x0 + xo + 94, y + 58), abbr, fit_font(abbr, "black", 50, 140), anchor="mm", alpha=255 * a)
            draw_text(d, (x0 + xo + 196, y + 50), name, fit_font(name, "semi", 28, 470), C.WHITE, anchor="ls", alpha=255 * a)
            draw_text(d, (x0 + xo + 196, y + 84), "STATUS", font("bold", 18), C.MUTED, anchor="ls", tracking=3, alpha=255 * a)
            # status pill
            pw, ph = 250, 50
            px1 = x1 + xo - 18
            d.rounded_rectangle((px1 - pw, y + 31, px1, y + 31 + ph), 25, fill=rgba(C.AMBER, 255 * a))
            dot = pulse(t, 1.3, 0.3, 1.0)
            d.ellipse((px1 - pw + 18, y + 48, px1 - pw + 34, y + 64), fill=rgba(C.NAVY_DEEP, 255 * a * dot))
            draw_text(d, (px1 - pw + 46, y + 57), "INVESTIGATING", font("black", 23), C.NAVY_DEEP,
                      anchor="lm", alpha=255 * a, tracking=1)

        a = ease_out(prog(t, 0.6, 0.45))
        if a > 0:
            y = 764
            panel(L, (x0, y, x1, y + 84), alpha=int(self.panel_alpha * a), accent=None)
            draw_text(d, (x0 + 24, y + 50), "CAUSE", font("bold", 20), C.MUTED, anchor="ls", tracking=3, alpha=255 * a)
            draw_text(d, (x0 + 124, y + 54), "UNDER INVESTIGATION", font("black", 38), C.WHITE, anchor="ls", alpha=255 * a)

        a = ease_out(prog(t, 0.85, 0.45))
        if a > 0:
            y = 864
            panel(L, (x0, y, x1, y + 156), alpha=int(self.panel_alpha * a), accent=C.RED)
            tag(L, (x0 + 22, y + 22), "CRASH SITE", size=20, pad=(12, 6), alpha=255 * a)
            draw_text(d, (x0 + 22, y + 102), "Military Trail & 10th Avenue North",
                      fit_font("Military Trail & 10th Avenue North", "xbold", 42, x1 - x0 - 44), C.WHITE,
                      anchor="ls", alpha=255 * a)
            chips = ["FIREBALL", "CRATER BY THE ROAD", "~600 EVACUATED"]
            cx = x0 + 22
            for c in chips:
                w = text_w(c, font("bold", 19), 1) + 24
                d.rounded_rectangle((cx, y + 116, cx + w, y + 146), 6, outline=rgba(C.MUTED, 255 * a), width=2)
                draw_text(d, (cx + 12, y + 132), c, font("bold", 19), C.OFFWHITE, anchor="lm", tracking=1, alpha=255 * a)
                cx += w + 10
            draw_text(d, (x1 - 22, y + 46), "GREENACRES, FL", font("bold", 20), C.MUTED, anchor="rm",
                      tracking=2, alpha=255 * a)

        self._outro(L, t)
        return L

    def _outro(self, L, t):
        a = ease_out(prog(t, self.t_outro, 0.55))
        if a <= 0:
            return
        d = ImageDraw.Draw(L)
        y0, y1 = 1040, 1180
        slide = -C.W * (1 - a)
        x0, x1 = C.MARGIN + slide, C.W - C.MARGIN + slide
        panel(L, (x0, y0, x1, y1), alpha=245, accent=None, fill=C.NAVY_DEEP, outline=C.RED)
        d.rounded_rectangle((x0, y0, x0 + 140, y1), 18, fill=rgba(C.RED))
        d.rectangle((x0 + 120, y0, x0 + 140, y1), fill=rgba(C.RED))
        # bell icon
        bx, by = x0 + 70, y0 + 66
        d.pieslice((bx - 30, by - 36, bx + 30, by + 24), 180, 360, fill=rgba(C.WHITE))
        d.rectangle((bx - 30, by - 6, bx + 30, by + 18), fill=rgba(C.WHITE))
        d.polygon([(bx - 40, by + 26), (bx + 40, by + 26), (bx + 30, by + 14), (bx - 30, by + 14)], fill=rgba(C.WHITE))
        d.ellipse((bx - 10, by + 28, bx + 10, by + 44), fill=rgba(C.WHITE))
        ring = pulse(t, 1.0)
        d.arc((bx - 52, by - 50, bx + 52, by + 50), 200, 240, fill=rgba(C.WHITE, 120 + 135 * ring), width=5)
        d.arc((bx - 52, by - 50, bx + 52, by + 50), 300, 340, fill=rgba(C.WHITE, 120 + 135 * ring), width=5)
        tx = x0 + 168
        draw_text(d, (tx, y0 + 64), "Follow Global News 1.0", fit_font("Follow Global News 1.0", "black", 50, x1 - tx - 24),
                  C.WHITE, anchor="ls")
        draw_text(d, (tx + 2, y0 + 110), "for Real-Time Updates", font("xbold", 34), C.AMBER, anchor="ls")


SCENE_CLASSES = {"map": MapScene, "telemetry": TelemetryScene,
                 "summary": SummaryScene, "investigation": InvestigationScene}
