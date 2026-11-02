"""The four animated scenes. Each draws onto an RGB frame for a local time t."""
from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import charts, geo
from .config import (W, MARGIN_X, KICKER_Y, HEADLINE_Y, LOWER_THIRD_Y, SceneSlot,
                     NAVY_DEEP, PANEL, PANEL_HI, CYAN, CYAN_DIM, NATO_BLUE, NATO_LIGHT,
                     AMBER, ALERT_RED, WHITE, GREY, rgba)
from .draw import (prog, ease_out, ease_in_out, ease_back, clamp, text, text_size, fit_size,
                   panel, brackets, chip, glow_layer, glow_line, check_icon, warn_icon,
                   bell_icon, flag, stamp)

CW = W - 2 * MARGIN_X  # content width (980)


class Scene:
    def __init__(self, T: dict, slot: SceneSlot, cues: dict[str, float]):
        self.T, self.slot, self._cues = T, slot, cues

    def cue(self, key: str, default: float, lead: float = 0.0) -> float:
        """Local time of a spoken keyword inside this scene (or a default)."""
        g = self._cues.get(key)
        if g is None or not (self.slot.start - 0.5 <= g <= self.slot.end):
            return default
        return max(0.0, g - self.slot.start - lead)

    # shared header block for each scene: kicker chip + headline
    def kicker_headline(self, img, d, t, kicker, lines, kicker_bg=AMBER, note=None, size=60):
        p = ease_out(prog(t, 0.05, 0.4))
        if p > 0:
            x = MARGIN_X - 80 * (1 - p)
            box = chip(d, (x, KICKER_Y), kicker, bg=kicker_bg, size=26, alpha=p)
            if note:
                blink = 0.75 + 0.25 * math.sin(t * 6)
                text(d, (box[2] + 18, (box[1] + box[3]) / 2), note, "mono", 22, CYAN, p * blink, anchor="lm")
        for i, line in enumerate(lines):
            pi = ease_out(prog(t, 0.25 + 0.15 * i, 0.45))
            if pi <= 0:
                continue
            sz = fit_size(line, "black", size, CW)
            y = HEADLINE_Y + i * (size + 8) + 30 * (1 - pi)
            text(d, (MARGIN_X, y), line, "black", sz, WHITE, pi, stroke=2, stroke_color=NAVY_DEEP)

    def draw(self, img: Image.Image, t: float) -> None:  # pragma: no cover
        raise NotImplementedError


# ═════════════════════════════════════════════════════════════════════════
class PackageScene(Scene):
    """Scene 1: 500 PAC-3 MSE • $2.1B • Lockheed Martin."""
    GRID_COLS, GRID_ROWS = 50, 10

    def draw(self, img, t):
        T = self.T
        d = ImageDraw.Draw(img, "RGBA")
        self.kicker_headline(img, d, t, T["s1_kicker"], T["s1_head"], kicker_bg=ALERT_RED,
                             note=T["s1_kicker_note"])

        # main card
        pc = ease_out(prog(t, 0.6, 0.5))
        card = (MARGIN_X, 490, W - MARGIN_X, 912)
        if pc > 0:
            panel(d, card, alpha=pc)
            text(d, (card[2] - 20, card[1] + 22), "FMS // PAC-3 MSE", "mono", 18, CYAN_DIM, pc, anchor="rm")

        # 500 counter, synced to the spoken "500"
        t500 = self.cue("count500", 3.2, lead=0.25)
        pcount = ease_in_out(prog(t, t500, 1.8))
        if pc > 0:
            n = int(round(500 * pcount))
            a = pc
            text(d, (card[0] + 30, card[1] + 120), f"{n:03d}" if n < 500 else "500", "black", 210,
                 CYAN, a, anchor="lm")
            labels = [(T["s1_patriot"], "black", 44, AMBER), (T["s1_model"], "black", 66, WHITE),
                      (T["s1_interceptors"], "xbold", 34, GREY)]
            ly = card[1] + 44
            for i, (s, st, sz, col) in enumerate(labels):
                pl = ease_out(prog(t, t500 + 0.15 * i, 0.4))
                sz = fit_size(s, st, sz, card[2] - 560 - 30)
                text(d, (560 + 40 * (1 - pl), ly), s, st, sz, col, pl)
                ly += sz + 12
            # pip grid: 1 pip = 1 interceptor
            gx0, gy0 = card[0] + 30, card[1] + 236
            cw = (card[2] - card[0] - 60) / self.GRID_COLS
            ch = 14.5
            lit = n
            for k in range(500):
                col, row = divmod(k, self.GRID_ROWS)
                x = gx0 + col * cw
                y = gy0 + row * ch
                if k < lit:
                    fresh = k > lit - 25
                    color = WHITE if fresh else (AMBER if (col + row) % 17 == 0 else CYAN)
                    d.rounded_rectangle((x + 2, y + 2, x + cw - 4, y + ch - 3), radius=3, fill=rgba(color, 235 * a))
                else:
                    d.rounded_rectangle((x + 2, y + 2, x + cw - 4, y + ch - 3), radius=3,
                                        outline=rgba(CYAN_DIM, 70 * a), width=1)
            gl = prog(t, t500 + 1.6, 0.4)
            text(d, (card[0] + 30, card[3] - 12), T["s1_grid_label"], "mono", 17, GREY, gl, anchor="lb")
            # scanning bar across the grid
            if pcount >= 1:
                sx = gx0 + ((t - t500) * 420) % (card[2] - card[0] + 200) - 100
                d.rectangle((sx, gy0 - 6, sx + 6, gy0 + self.GRID_ROWS * ch + 4), fill=rgba(WHITE, 90))

        # value tile ($2.1B) and contractor tile
        tv = self.cue("value", 2.0, lead=0.15)
        tl = self.cue("lockheed", 7.6, lead=0.2)
        tiles = [(MARGIN_X, 930, 530, 1140, tv), (550, 930, W - MARGIN_X, 1140, tl)]
        for idx, (x0, y0, x1, y1, ts) in enumerate(tiles):
            p = ease_back(prog(t, ts, 0.5))
            if p <= 0:
                continue
            a = clamp(p)
            yoff = 40 * (1 - clamp(p))
            box = (x0, y0 + yoff, x1, y1 + yoff)
            d.rectangle(box, fill=rgba(PANEL_HI if idx else NAVY_DEEP, 225 * a),
                        outline=rgba(AMBER if idx == 0 else NATO_LIGHT, 220 * a), width=3)
            d.rectangle((x0, box[1], x0 + 10, box[3]), fill=rgba(AMBER if idx == 0 else NATO_LIGHT, 255 * a))
            if idx == 0:
                v = 2.1 * ease_out(prog(t, ts, 1.1))
                val = T["s1_value_fmt"].format(v=v).replace(".", "," if "BI" in T["s1_value_fmt"] else ".")
                sz = fit_size(T["s1_value_fmt"].format(v=2.1), "black", 104, x1 - x0 - 50)
                text(d, (x0 + 32, box[1] + 92), val, "black", sz, AMBER, a, anchor="lm")
                text(d, (x0 + 34, box[3] - 26), T["s1_value_label"], "mono", 22, WHITE, a, anchor="lb")
            else:
                for j, line in enumerate(T["s1_contractor"]):
                    text(d, (x0 + 32, box[1] + 30 + j * 56), line, "black", 52, WHITE, a)
                text(d, (x0 + 34, box[3] - 26), T["s1_contractor_label"], "mono", 22, CYAN, a, anchor="lb")

        ps = prog(t, tl + 1.2, 0.5)
        text(d, (W - MARGIN_X, 1160), T["s1_source"], "mono", 16, GREY, ps * 0.9, anchor="rt")


# ═════════════════════════════════════════════════════════════════════════
class MoneyScene(Scene):
    """Scene 2: funding flow map — Canada, Germany, Norway, EU → Kyiv; $0 US."""
    MAP_X, MAP_Y = MARGIN_X, 432
    FLAG_OFFS = {"CA": (18, 14), "NO": (-70, -40), "DE": (-6, 16), "EU": (-74, 6), "US": (-20, 20)}

    def __init__(self, T, slot, cues):
        super().__init__(T, slot, cues)
        self.map_img = geo.render_funding_map()
        self.nodes = {k: self._abs(*geo.map_px(lat, lon)) for k, (_, lat, lon) in geo.CITIES.items()}
        self.arcs = {}
        kx, ky = self.nodes["UA"]
        for code in ("CA", "DE", "NO", "EU"):
            sx, sy = self.nodes[code]
            dist = math.hypot(kx - sx, ky - sy)
            cx, cy = (sx + kx) / 2, min(sy, ky) - 0.28 * dist - 20
            ts = np.linspace(0, 1, 80)
            pts = [((1 - u) ** 2 * sx + 2 * (1 - u) * u * cx + u ** 2 * kx,
                    (1 - u) ** 2 * sy + 2 * (1 - u) * u * cy + u ** 2 * ky) for u in ts]
            self.arcs[code] = pts
        self._arc_cache: dict[str, tuple] = {}

    def _abs(self, x, y):
        return (self.MAP_X + x, self.MAP_Y + y)

    def draw(self, img, t):
        T = self.T
        d = ImageDraw.Draw(img, "RGBA")
        self.kicker_headline(img, d, t, T["s2_kicker"], T["s2_head"], size=62)

        pm = ease_out(prog(t, 0.35, 0.6))
        box = (self.MAP_X, self.MAP_Y, self.MAP_X + geo.MAP_W, self.MAP_Y + geo.MAP_H)
        if pm > 0:
            m = self.map_img
            if pm < 1:
                m = m.copy()
                m.putalpha(m.getchannel("A").point(lambda v: int(v * pm)))
            img.paste(m, box[:2], m)
            d.rectangle(box, outline=rgba(CYAN, 120 * pm), width=2)
            brackets(d, box, CYAN, pm)
            text(d, (box[0] + 14, box[3] - 12), T["s2_map_note"], "mono", 16, GREY, pm, anchor="lb")

        starts = {"CA": self.cue("canada", 2.6, 0.1), "DE": self.cue("germany", 3.3, 0.1),
                  "NO": self.cue("norway", 4.0, 0.1), "EU": self.cue("eu", 4.7, 0.1)}
        t_zero = self.cue("zero", 1.4, 0.1)

        # US node: $0
        pu = ease_out(prog(t, t_zero, 0.4))
        if pu > 0:
            ux, uy = self.nodes["US"]
            r = 7 + 3 * math.sin(t * 5)
            d.ellipse((ux - r, uy - r, ux + r, uy + r), fill=rgba(GREY, 230 * pu), outline=rgba(WHITE, 200 * pu))
            fx, fy = self.FLAG_OFFS["US"]
            flag(img, "US", (ux + fx, uy + fy, ux + fx + 42, uy + fy + 26), pu)
            text(d, (ux + fx + 52, uy + fy + 13), T["s2_usa"], "black", 30, AMBER, pu, anchor="lm",
                 stroke=3, stroke_color=NAVY_DEEP)

        # arcs and money packets
        for code, pts in self.arcs.items():
            p = ease_in_out(prog(t, starts[code], 0.9))
            if p <= 0:
                continue
            sx, sy = self.nodes[code]
            if p >= 1:
                if code not in self._arc_cache:
                    self._arc_cache[code] = glow_layer(pts, CYAN, 4, 0.9, 10)
                layer, lx, ly = self._arc_cache[code]
                img.paste(layer, (lx, ly), layer)
            else:
                k = max(2, int(len(pts) * p))
                glow_line(img, pts[:k], CYAN, 4, 0.9, 10)
            # packets travelling to Kyiv
            if p >= 1:
                for j in range(3):
                    u = ((t - starts[code]) * 0.55 + j / 3) % 1.0
                    idx = int(u * (len(pts) - 1))
                    px, py = pts[idx]
                    d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=rgba(AMBER, 240), outline=rgba(WHITE, 200))
            # source node + flag
            pn = ease_back(prog(t, starts[code], 0.4))
            r = 9 * clamp(pn)
            d.ellipse((sx - r, sy - r, sx + r, sy + r), fill=rgba(CYAN, 255), outline=rgba(WHITE, 255), width=2)
            fx, fy = self.FLAG_OFFS[code]
            flag(img, code, (sx + fx, sy + fy, sx + fx + 52, sy + fy + 32), clamp(pn))

        # Kyiv target
        pk = ease_out(prog(t, starts["CA"] - 0.3, 0.4))
        if pk > 0:
            kx, ky = self.nodes["UA"]
            for j in range(3):
                ph = ((t * 0.8) + j / 3) % 1.0
                rr = 10 + 46 * ph
                d.ellipse((kx - rr, ky - rr, kx + rr, ky + rr), outline=rgba(AMBER, 230 * (1 - ph) * pk), width=3)
            d.ellipse((kx - 10, ky - 10, kx + 10, ky + 10), fill=rgba(AMBER, 255 * pk), outline=rgba(WHITE, 255 * pk), width=2)
            text(d, (kx, ky - 58), T["s2_kyiv"], "black", 30, WHITE, pk, anchor="mm", stroke=4, stroke_color=NAVY_DEEP)

        # $0 stamp over the Atlantic
        ps = prog(t, t_zero + 0.1, 0.35)
        if ps > 0:
            sc = 1.6 - 0.6 * ease_out(ps)
            stamp(img, (self.MAP_X + 380, self.MAP_Y + 330), T["s2_stamp"], ALERT_RED, clamp(ps * 1.5), -8, 0.82 * sc)

        # funder chips
        cw = (CW - 3 * 12) / 4
        for i, (code, name, sub) in enumerate(T["s2_funders"]):
            ts = starts[code]
            p = ease_back(prog(t, ts, 0.45))
            if p <= 0:
                continue
            x0 = MARGIN_X + i * (cw + 12)
            y0 = 928 + 30 * (1 - clamp(p))
            a = clamp(p)
            arrived = prog(t, ts + 0.9, 0.3)
            d.rectangle((x0, y0, x0 + cw, y0 + 104), fill=rgba(PANEL, 230 * a),
                        outline=rgba(CYAN if arrived < 1 else AMBER, (140 + 100 * arrived) * a), width=2)
            flag(img, code, (x0 + 14, y0 + 14, x0 + 14 + 58, y0 + 14 + 36), a)
            if arrived >= 1:
                check_icon(d, x0 + cw - 26, y0 + 30, 26, AMBER, a, w=5)
            nsz = fit_size(name, "black", 30, int(cw - 24))
            text(d, (x0 + 14, y0 + 64), name, "black", nsz, WHITE, a, anchor="lm")
            if sub:
                ssz = fit_size(sub, "mono", 15, int(cw - 24))
                text(d, (x0 + 14, y0 + 90), sub, "mono", ssz, CYAN, a, anchor="lm")

        # total bar
        tb = ease_out(prog(t, starts["EU"] + 0.9, 0.8))
        if tb > 0:
            bx0, by0, bx1, by1 = MARGIN_X, 1048, W - MARGIN_X, 1140
            d.rectangle((bx0, by0, bx1, by1), fill=rgba(NAVY_DEEP, 220), outline=rgba(NATO_LIGHT, 200), width=2)
            d.rectangle((bx0 + 4, by0 + 4, bx0 + 4 + (bx1 - bx0 - 8) * tb, by1 - 4), fill=rgba(NATO_BLUE, 235))
            sz = fit_size(T["s2_total"], "black", 40, CW - 40)
            text(d, ((bx0 + bx1) / 2, (by0 + by1) / 2), T["s2_total"], "black", sz, WHITE, clamp(tb * 1.4), anchor="mm")


# ═════════════════════════════════════════════════════════════════════════
class TimelineScene(Scene):
    """Scene 3: immediate need vs 2030s deliveries; stockpile swap & backfill."""
    CX, CY = MARGIN_X, 506

    def __init__(self, T, slot, cues):
        super().__init__(T, slot, cues)
        self.base, self.plan = charts.render_timeline(T)

    def draw(self, img, t):
        T = self.T
        d = ImageDraw.Draw(img, "RGBA")
        self.kicker_headline(img, d, t, T["s3_kicker"], T["s3_head"], kicker_bg=ALERT_RED, size=62)

        cbox = (self.CX - 10, self.CY - 14, self.CX + charts.CHART_W + 10, self.CY + charts.CHART_H + 8)
        pp = ease_out(prog(t, 0.3, 0.4))
        if pp > 0:
            d.rectangle(cbox, fill=rgba(NAVY_DEEP, 205 * pp), outline=rgba(CYAN, 90 * pp), width=2)
            brackets(d, cbox, CYAN, pp)

        # left-to-right wipe of the chart
        pw = ease_in_out(prog(t, 0.45, 2.2))
        if pw > 0:
            wpx = int(charts.CHART_W * pw)
            if wpx > 1:
                part = self.base.crop((0, 0, wpx, charts.CHART_H))
                img.paste(part, (self.CX, self.CY), part)
                if pw < 1:
                    x = self.CX + wpx
                    d.rectangle((x - 2, self.CY, x + 2, self.CY + charts.CHART_H - 40), fill=rgba(CYAN, 230))

        # NOW marker
        pn = prog(t, 0.8, 0.4)
        if pn > 0:
            nx = self.CX + charts.chart_x(charts.NOW)
            pulse = 0.65 + 0.35 * math.sin(t * 7)
            y = self.CY + 22
            while y < self.CY + charts.CHART_H - 42:
                d.line([(nx, y), (nx, y + 12)], fill=rgba(ALERT_RED, 255 * pn * pulse), width=4)
                y += 20
            chip(d, (nx - 40, self.CY - 30), T["s3_now"], fg=WHITE, bg=ALERT_RED, size=22, alpha=pn, pad=(10, 4))

        # the gap bracket (NOW → 2030s) on the production lane
        tg = self.cue("2030s", 4.2, 0.1)
        pg = ease_out(prog(t, tg, 0.5))
        if pg > 0:
            x0 = self.CX + charts.chart_x(charts.NOW)
            x1 = self.CX + charts.chart_x(charts.DECADE)
            yb = self.CY + charts.chart_y(charts.LANES["prod"]) + 34
            xm = x0 + (x1 - x0) * pg
            flash = 0.7 + 0.3 * math.sin(t * 9)
            d.line([(x0, yb - 10), (x0, yb), (xm, yb)], fill=rgba(ALERT_RED, 255 * flash), width=4)
            if pg >= 1:
                d.line([(x1, yb), (x1, yb - 10)], fill=rgba(ALERT_RED, 255 * flash), width=4)
                chip(d, ((x0 + x1) / 2 - 70, yb + 4), T["s3_gap"], fg=WHITE, bg=ALERT_RED, size=20,
                     alpha=flash, pad=(10, 3))

        # proposal lane wipe
        tk = self.cue("kyiv", 6.2, 0.1)
        pl = ease_in_out(prog(t, tk, 1.4))
        if pl > 0:
            wpx = int(charts.CHART_W * pl)
            if wpx > 1:
                part = self.plan.crop((0, 0, wpx, charts.CHART_H))
                img.paste(part, (self.CX, self.CY), part)

        # swap & backfill flow
        self._flow(img, d, t, tk, self.cue("backfill", 9.2, 0.1))

    def _flow(self, img, d, t, tk, tb):
        T = self.T
        pt = ease_out(prog(t, tk, 0.5))
        if pt <= 0:
            return
        title = T["s3_flow_title"]
        text(d, (MARGIN_X, 924), title, "xbold", fit_size(title, "xbold", 28, CW), AMBER, pt)
        bw, by0, by1 = 250, 968, 1058
        xs = [MARGIN_X, (W - bw) / 2, W - MARGIN_X - bw]
        appear = [tb, tk, tk + 0.25]
        colors = [CYAN, NATO_LIGHT, AMBER]
        for i, ((l1, l2), x0) in enumerate(zip(T["s3_nodes"], xs)):
            p = ease_back(prog(t, appear[i], 0.45))
            if p <= 0:
                continue
            a = clamp(p)
            yo = 24 * (1 - a)
            d.rectangle((x0, by0 + yo, x0 + bw, by1 + yo), fill=rgba(PANEL, 235 * a),
                        outline=rgba(colors[i], 230 * a), width=3)
            text(d, (x0 + bw / 2, by0 + 34 + yo), l1, "black", fit_size(l1, "black", 34, bw - 20),
                 WHITE, a, anchor="mm")
            text(d, (x0 + bw / 2, by0 + 70 + yo), l2, "mono", fit_size(l2, "mono", 18, bw - 20),
                 colors[i], a, anchor="mm")
        ym = (by0 + by1) / 2
        arrows = [(xs[0] + bw, xs[1], tb + 0.3, CYAN, T["s3_arrows"][0]),
                  (xs[1] + bw, xs[2], tk + 0.5, AMBER, T["s3_arrows"][1])]
        for (ax0, ax1, ta, col, (lab1, lab2)) in arrows:
            p = ease_out(prog(t, ta, 0.6))
            if p <= 0:
                continue
            x_end = ax0 + 8 + (ax1 - ax0 - 16) * p
            d.line([(ax0 + 8, ym), (x_end, ym)], fill=rgba(col, 255), width=6)
            d.polygon([(x_end + 4, ym), (x_end - 16, ym - 13), (x_end - 16, ym + 13)], fill=rgba(col, 255))
            if p >= 1:
                for j in range(2):
                    u = ((t - ta) * 0.9 + j / 2) % 1.0
                    px = ax0 + 12 + (ax1 - ax0 - 40) * u
                    d.ellipse((px - 6, ym - 6, px + 6, ym + 6), fill=rgba(WHITE, 230))
            mx = (ax0 + ax1) / 2
            text(d, (mx, by1 + 28), lab1, "black", 24, col, p, anchor="mm")
            text(d, (mx, by1 + 58), lab2, "mono", 20, WHITE, p, anchor="mm")


# ═════════════════════════════════════════════════════════════════════════
class ImpactScene(Scene):
    """Scene 4: integrated air-defense shield summary + follow lower-third."""
    SCOPE = 420
    SX, SY = MARGIN_X, 492
    BLIPS = [(50.45, 30.52), (49.99, 36.23), (46.48, 30.72), (49.84, 24.03), (48.46, 35.05),
             (47.84, 35.14), (51.50, 31.29), (46.64, 32.61)]

    def __init__(self, T, slot, cues):
        super().__init__(T, slot, cues)
        self.scope_img = geo.render_scope_map(self.SCOPE)
        s = self.SCOPE
        sweep = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        yy, xx = np.mgrid[0:s, 0:s]
        cx = cy = (s - 1) / 2
        ang = (np.degrees(np.arctan2(cy - yy, xx - cx)) + 360) % 360  # 0 = east, CCW
        rad = np.hypot(xx - cx, yy - cy)
        trail = np.clip(1 - ang / 70.0, 0, 1) ** 2
        alpha = (trail * 150 * (rad < s / 2 - 4)).astype(np.uint8)
        arr = np.zeros((s, s, 4), np.uint8)
        arr[..., 0], arr[..., 1], arr[..., 2], arr[..., 3] = CYAN[0], CYAN[1], CYAN[2], alpha
        self.sweep = Image.fromarray(arr, "RGBA")
        self.blip_px = [geo.scope_px(lat, lon, s) for lat, lon in self.BLIPS]

    def draw(self, img, t):
        T = self.T
        d = ImageDraw.Draw(img, "RGBA")
        self.kicker_headline(img, d, t, T["s4_kicker"], T["s4_head"], kicker_bg=NATO_LIGHT, size=60)

        # radar scope
        ps = ease_out(prog(t, 0.4, 0.6))
        if ps > 0:
            s = self.SCOPE
            m = self.scope_img
            if ps < 1:
                m = m.copy()
                m.putalpha(m.getchannel("A").point(lambda v: int(v * ps)))
            img.paste(m, (self.SX, self.SY), m)
            heading = (t * 120) % 360  # degrees, CCW from east
            sw = self.sweep.rotate(heading, resample=Image.BILINEAR)
            if ps < 1:
                sw.putalpha(sw.getchannel("A").point(lambda v: int(v * ps)))
            img.paste(sw, (self.SX, self.SY), sw)
            c = s / 2
            for bx, by in self.blip_px:
                ba = (math.degrees(math.atan2(c - by, bx - c)) + 360) % 360
                since = ((heading - ba) % 360) / 120.0  # seconds since sweep passed
                a = clamp(1 - since / 1.6) * ps
                if a > 0:
                    x, y = self.SX + bx, self.SY + by
                    d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=rgba(WHITE, 255 * a))
                    d.ellipse((x - 14, y - 14, x + 14, y + 14), outline=rgba(CYAN, 200 * a), width=2)
            # shield dome pulses after "shield"
            tsh = self.cue("shield", 3.8, 0.1)
            if t > tsh:
                for j in range(2):
                    ph = ((t - tsh) * 0.6 + j / 2) % 1.0
                    r = 40 + (s / 2 - 50) * ph
                    d.ellipse((self.SX + c - r, self.SY + c - r, self.SX + c + r, self.SY + c + r),
                              outline=rgba(AMBER, 200 * (1 - ph)), width=3)
            text(d, (self.SX + s / 2, self.SY + s + 22), T["s4_scope"], "mono", 18, CYAN, ps, anchor="mm")

        # defense tiers
        tx0, tx1 = self.SX + self.SCOPE + 26, W - MARGIN_X
        th = 124
        for i, (tier, sysname, badge) in enumerate(T["s4_tiers"]):
            p = ease_out(prog(t, 0.7 + 0.25 * i, 0.5))
            if p <= 0:
                continue
            y0 = self.SY + i * (th + 14)
            x0 = tx0 + 60 * (1 - p)
            hi = i == 0
            pulse = 0.75 + 0.25 * math.sin(t * 5) if hi else 1.0
            d.rectangle((x0, y0, tx1, y0 + th), fill=rgba(PANEL_HI if hi else PANEL, 230 * p),
                        outline=rgba(AMBER if hi else CYAN_DIM, (240 * pulse if hi else 140) * p), width=3 if hi else 2)
            d.rectangle((x0, y0, x0 + 8, y0 + th), fill=rgba(AMBER if hi else NATO_LIGHT, 255 * p))
            text(d, (x0 + 24, y0 + 34), tier, "mono", fit_size(tier, "mono", 20, int(tx1 - x0 - 140)),
                 AMBER if hi else CYAN, p, anchor="lm")
            text(d, (x0 + 24, y0 + 80), sysname, "black", fit_size(sysname, "black", 30, int(tx1 - x0 - 40)),
                 WHITE if hi else GREY, p, anchor="lm")
            if badge:
                bx = tx1 - 104
                d.rectangle((bx, y0 + 14, tx1 - 14, y0 + 56), fill=rgba(AMBER, 255 * p))
                text(d, ((bx + tx1 - 14) / 2, y0 + 35), badge, "black", 28, NAVY_DEEP, p, anchor="mm")

        # summary checklist
        ys = 948
        for i, (kind, line) in enumerate(T["s4_checks"]):
            p = ease_out(prog(t, 1.4 + 0.45 * i, 0.4))
            if p <= 0:
                continue
            y = ys + i * 50
            x = MARGIN_X + 40 * (1 - p)
            col = CYAN if kind == "ok" else AMBER
            d.rectangle((x, y - 22, W - MARGIN_X, y + 22), fill=rgba(NAVY_DEEP, 190 * p))
            if kind == "ok":
                check_icon(d, x + 24, y, 26, col, p, w=5)
            else:
                warn_icon(d, x + 24, y, 34, AMBER, p)
            sz = fit_size(line, "xbold", 30, CW - 80)
            text(d, (x + 58, y), line, "xbold", sz, WHITE if kind == "ok" else AMBER, p, anchor="lm")

        # lower third: follow
        tf = min(self.cue("follow", 8.6, 0.3), self.slot.dur - 2.5)
        pf = ease_out(prog(t, tf, 0.5))
        if pf > 0:
            y0, y1 = LOWER_THIRD_Y, LOWER_THIRD_Y + 118
            x1 = MARGIN_X + (CW) * pf
            d.rectangle((MARGIN_X, y0, x1, y1), fill=rgba(NATO_BLUE, 245))
            d.rectangle((MARGIN_X, y0, x1, y0 + 6), fill=rgba(CYAN, 255))
            d.rectangle((MARGIN_X, y0, MARGIN_X + 110, y1), fill=rgba(AMBER, 255 * pf))
            ring = 0.5 + 0.5 * math.sin(t * 8)
            bell_icon(d, MARGIN_X + 55, y0 + 60, 54 + 4 * ring, NAVY_DEEP, pf)
            pt = prog(t, tf + 0.3, 0.4)
            l1, l2 = T["lower_third"]
            text(d, (MARGIN_X + 136, y0 + 42), l1, "black", fit_size(l1, "black", 44, CW - 160), WHITE, pt, anchor="lm")
            text(d, (MARGIN_X + 138, y0 + 88), l2, "mono", fit_size(l2, "mono", 26, CW - 160), CYAN, pt, anchor="lm")


SCENE_CLASSES = {
    "package": PackageScene,
    "money": MoneyScene,
    "timeline": TimelineScene,
    "impact": ImpactScene,
}
