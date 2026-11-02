"""Frame-by-frame broadcast graphics (Pillow + matplotlib + numpy)."""
import io
import math
from functools import lru_cache
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

from .content import FACTS, SCENES, TEXT, fmt_num  # noqa: E402

W, H = 1080, 1920

# Palette
CHARCOAL = (17, 17, 19)
CHARCOAL_2 = (38, 37, 41)
TRACK = (52, 51, 56)
CRIMSON = (204, 18, 48)
CRIMSON_DK = (110, 8, 24)
WHITE = (246, 244, 239)
GOLD = (247, 192, 32)
GREY = (150, 148, 152)
BLACK = (0, 0, 0)

FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
_FALLBACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# --------------------------------------------------------------------------- fonts
@lru_cache(maxsize=None)
def font(kind, size, weight=600):
    path = FONT_DIR / ("Anton-Regular.ttf" if kind == "anton" else "Oswald-Variable.ttf")
    try:
        f = ImageFont.truetype(str(path), size)
        if kind != "anton":
            try:
                f.set_variation_by_axes([weight])
            except Exception:
                pass
        return f
    except OSError:
        return ImageFont.truetype(_FALLBACK, int(size * 0.85))


def _register_mpl_fonts():
    p = FONT_DIR / "Anton-Regular.ttf"
    if p.exists():
        font_manager.fontManager.addfont(str(p))
        return font_manager.FontProperties(fname=str(p))
    return font_manager.FontProperties(family="DejaVu Sans", weight="bold")


MPL_FONT = _register_mpl_fonts()


# --------------------------------------------------------------------------- easing
def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, a, b):
    return clamp((t - a) / (b - a)) if b > a else float(t >= a)


def ease_out(p):
    return 1 - (1 - p) ** 3


def ease_in_out(p):
    return 4 * p ** 3 if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_back(p, s=1.9):
    p -= 1
    return 1 + (s + 1) * p ** 3 + s * p ** 2


def lerp(a, b, p):
    return a + (b - a) * p


# --------------------------------------------------------------------------- text helpers
@lru_cache(maxsize=4096)
def text_img(text, kind, size, fill, weight=600, stroke=0, stroke_fill=BLACK, shadow=0):
    f = font(kind, size, weight)
    l, t, r, b = f.getbbox(text, stroke_width=stroke)
    pad = 4 + shadow
    img = Image.new("RGBA", (r - l + pad * 2, b - t + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if shadow:
        sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((pad - l + shadow, pad - t + shadow), text, font=f,
                                fill=(0, 0, 0, 200), stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(shadow / 2)))
        d = ImageDraw.Draw(img)
    d.text((pad - l, pad - t), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
    return img


def fit_size(text, kind, size, max_w, weight=600):
    while size > 12 and font(kind, size, weight).getlength(text) > max_w:
        size -= 2
    return size


def with_alpha(img, a):
    if a >= 0.999:
        return img
    img = img.copy()
    img.putalpha(img.getchannel("A").point(lambda v: int(v * a)))
    return img


def place(layer, img, x, y, anchor="lt", alpha=1.0, scale=1.0, rotate=0.0):
    """Composite `img` onto `layer` with anchor in {l,m,r}x{t,m,b}."""
    if alpha <= 0.003:
        return
    if scale != 1.0:
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        img = img.resize((nw, nh), Image.BICUBIC)
    if rotate:
        img = img.rotate(rotate, resample=Image.BICUBIC, expand=True)
    img = with_alpha(img, alpha)
    ax, ay = anchor[0], anchor[1]
    x0 = x - (img.width / 2 if ax == "m" else img.width if ax == "r" else 0)
    y0 = y - (img.height / 2 if ay == "m" else img.height if ay == "b" else 0)
    x0, y0 = int(round(x0)), int(round(y0))
    # clip to layer
    sx, sy = max(0, -x0), max(0, -y0)
    ex, ey = min(img.width, layer.width - x0), min(img.height, layer.height - y0)
    if ex <= sx or ey <= sy:
        return
    if sx or sy or ex < img.width or ey < img.height:
        img = img.crop((sx, sy, ex, ey))
    layer.alpha_composite(img, (x0 + sx, y0 + sy))


def rgba(c, a=1.0):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


# --------------------------------------------------------------------------- static plates
def background_plate(seed=3):
    rng = np.random.default_rng(seed)
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    base = np.array(CHARCOAL, np.float32)
    glow = np.exp(-(((x - 0.15) / 0.6) ** 2 + ((y - 0.30) / 0.35) ** 2))
    plate = base[None, None, :] + glow[..., None] * np.array([38, 6, 10], np.float32)
    # faint diagonal hazard stripes + blotchy texture
    stripes = ((x * W + y * H) // 26 % 2).astype(np.float32) * 3.0
    blot = rng.standard_normal((H // 16, W // 16)).astype(np.float32)
    blot = np.array(Image.fromarray(blot).resize((W, H), Image.BICUBIC)) * 4.0
    plate += (stripes + blot)[..., None]
    img = Image.fromarray(np.clip(plate, 0, 255).astype(np.uint8)).convert("RGBA")
    d = ImageDraw.Draw(img, "RGBA")
    # halftone dot field in the lower area
    for yy in range(1300, H, 22):
        for xx in range(0, W, 22):
            r = 1 + 4 * ((yy - 1300) / (H - 1300))
            d.ellipse((xx - r, yy - r, xx + r, yy + r), fill=(255, 255, 255, 10))
    place(img, text_img("GN 1.0", "anton", 300, (255, 255, 255, 14)), W // 2, 1800, "mm")
    return np.array(img.convert("RGB"))


def vignette_mask():
    y = np.linspace(-1, 1, H)[:, None]
    x = np.linspace(-1, 1, W)[None, :]
    v = 1 - 0.55 * np.clip((x ** 2 * 0.9 + y ** 2 * 0.6) - 0.15, 0, None)
    v = np.clip(v, 0.35, 1.0)
    v = np.repeat(v, 1, axis=0)
    scan = np.ones((H, 1), np.float32)
    scan[::4] = 0.94
    return (v * scan * 256).astype(np.uint16)[..., None]


def grain_textures(n=8, sigma=6.0, seed=11):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        g = rng.normal(0, sigma, (H // 2, W // 2)).astype(np.float32)
        g = np.array(Image.fromarray(g).resize((W, H), Image.BILINEAR))
        g += rng.normal(0, sigma * 0.4, (H, W)).astype(np.float32)
        out.append(np.clip(g, -40, 40).astype(np.int16)[..., None])
    return out


# --------------------------------------------------------------------------- matplotlib chart
@lru_cache(maxsize=64)
def abstention_chart(step, lang, steps=40):
    p = step / steps
    a1, a2 = FACTS["abstention_r1"], FACTS["abstention_r2"]
    fig = plt.figure(figsize=(4.6, 5.0), dpi=100)
    fig.patch.set_alpha(0)
    ax = fig.add_axes([0.16, 0.12, 0.78, 0.82])
    ax.patch.set_alpha(0)
    ax.set_xlim(-0.25, 1.25)
    ax.set_ylim(17.5, 22.5)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#77757a")
    ax.tick_params(colors="#c9c7cc", length=0, labelsize=13)
    ax.set_yticks([18, 19, 20, 21, 22])
    ax.set_yticklabels([f"{v}%" for v in (18, 19, 20, 21, 22)], fontproperties=MPL_FONT, fontsize=14)
    ax.grid(axis="y", color="#ffffff", alpha=0.08, lw=1)
    t = TEXT[lang]
    ax.set_xticks([0, 1])
    ax.set_xticklabels([t["s2_r1"], t["s2_r2"]], fontproperties=MPL_FONT, fontsize=17, color="#f6f4ef")
    pe = ease_in_out(p)
    xs = np.linspace(0, pe, 30)
    ys = a1 + (a2 - a1) * xs
    ax.fill_between(xs, ys, 17.5, color="#cc1230", alpha=0.18, lw=0)
    ax.plot(xs, ys, color="#cc1230", lw=6, solid_capstyle="round")
    ax.scatter([0], [a1], s=220, color="#f6f4ef", zorder=5, edgecolor="#111113", lw=3)
    ax.text(0, a1 + 0.35, f"{fmt_num(a1, lang, 2)}%", ha="center", va="bottom",
            fontproperties=MPL_FONT, fontsize=26, color="#f6f4ef")
    if p >= 0.999:
        ax.scatter([1], [a2], s=320, color="#f7c020", zorder=6, edgecolor="#111113", lw=3)
        ax.text(1, a2 - 0.35, f"{fmt_num(a2, lang, 1)}%", ha="center", va="top",
                fontproperties=MPL_FONT, fontsize=30, color="#f7c020")
        ax.text(0.5, (a1 + a2) / 2 + 0.55, f"−{fmt_num(round(a1 - a2, 2), lang, 2)} PTS",
                ha="center", va="bottom", rotation=-14, fontproperties=MPL_FONT, fontsize=19,
                color="#ff4a64")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    buf.seek(0)
    return Image.open(buf).convert("RGBA")


# --------------------------------------------------------------------------- shapes
def ring(d, cx, cy, r, width, frac, color, track=TRACK):
    box = (cx - r, cy - r, cx + r, cy + r)
    d.arc(box, 0, 360, fill=rgba(track), width=width)
    if frac > 0:
        d.arc(box, -90, -90 + 360 * frac, fill=rgba(color), width=width)


def bus_icon(size=64, color=GOLD):
    s = size
    img = Image.new("RGBA", (int(s * 1.6), s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    w = img.width
    d.rounded_rectangle((2, 2, w - 3, s * 0.80), radius=int(s * 0.14), fill=color)
    for i in range(4):
        x0 = 8 + i * (w - 16) / 4
        d.rectangle((x0 + 3, s * 0.16, x0 + (w - 16) / 4 - 3, s * 0.42), fill=CHARCOAL)
    d.rectangle((6, s * 0.55, w - 7, s * 0.60), fill=CHARCOAL)
    for x in (w * 0.24, w * 0.76):
        d.ellipse((x - s * 0.13, s * 0.68, x + s * 0.13, s * 0.94), fill=CHARCOAL,
                  outline=color, width=max(2, s // 16))
    return img


# --------------------------------------------------------------------------- scene renderers
def kicker(layer, d, txt, lt):
    p = ease_out(prog(lt, 0.0, 0.45))
    f = font("oswald", 34, 650)
    tw = f.getlength(txt)
    x = 60 - (1 - p) * (tw + 120)
    d.rectangle((x, 352, x + 12, 400), fill=rgba(GOLD))
    d.rectangle((x + 18, 352, x + 18 + tw + 32, 400), fill=rgba(CRIMSON))
    d.text((x + 34, 376), txt, font=f, fill=WHITE, anchor="lm")


def scene1(layer, lt, lang):
    T = TEXT[lang]
    d = ImageDraw.Draw(layer, "RGBA")
    kicker(layer, d, T["s1_kicker"], lt)
    p = ease_out(prog(lt, 0.3, 1.0))
    place(layer, text_img(T["s1_title"], "anton", fit_size(T["s1_title"], "anton", 92, 900), WHITE,
                          shadow=6), 90 + (1 - p) * 60, 430, "lt", alpha=p)

    x0, full = 90, 900
    rows = [
        (T["s1_flavio"], FACTS["flavio_pct"], FACTS["flavio_votes_m"], (226, 224, 220), CHARCOAL, 625),
        (T["s1_lula"], FACTS["lula_pct"], FACTS["lula_votes_m"], CRIMSON, WHITE, 805),
    ]
    for i, (name, pct, votes, col, tcol, y) in enumerate(rows):
        a = prog(lt, 0.9 + i * 0.25, 1.4 + i * 0.25)
        if a <= 0:
            continue
        nf = font("oswald", 40, 650)
        d.text((x0, y - 18), name, font=nf, fill=rgba(WHITE, a), anchor="lb")
        d.text((x0 + full, y - 18), T["s1_votes"].format(v=fmt_num(votes, lang)),
               font=font("oswald", 34, 500), fill=rgba(GREY, a), anchor="rb")
        d.rectangle((x0, y, x0 + full, y + 80), fill=rgba(TRACK, a * 0.9))
        g = ease_out(prog(lt, 1.3 + i * 0.35, 3.3 + i * 0.35))
        bw = full * (pct / 50.0) * g
        d.rectangle((x0, y, x0 + bw, y + 80), fill=rgba(col, a))
        if g > 0.25:
            val = f"{fmt_num(pct * g, lang, 2)}%"
            d.text((x0 + bw - 16, y + 40), val, font=font("anton", 56), fill=rgba(tcol, a), anchor="rm")

    # deficit highlight + callout
    pg = ease_out(prog(lt, 3.9, 4.5))
    if pg > 0:
        xa = x0 + full * FACTS["lula_pct"] / 50
        xb = x0 + full * FACTS["flavio_pct"] / 50
        d.rectangle((xa, 805, xa + (xb - xa) * pg, 885), outline=rgba(GOLD), width=4)
        for k in range(int(xa), int(xa + (xb - xa) * pg), 10):
            d.line((k, 885, min(k + 18, xb), 805), fill=rgba(GOLD, 0.7), width=3)
        d.line((xb, 705, xb, 905), fill=rgba(GOLD, pg), width=3)
        gap_pts = fmt_num(round(FACTS["flavio_pct"] - FACTS["lula_pct"], 2), lang, 2)
        gap_v = fmt_num(round(FACTS["flavio_votes_m"] - FACTS["lula_votes_m"], 1), lang, 1)
        txt = T["s1_gap"].format(pts=gap_pts, votes=gap_v)
        place(layer, text_img(txt, "anton", fit_size(txt, "anton", 52, 900), GOLD, shadow=4),
              x0 + full, 925, "rt", alpha=pg, scale=lerp(1.25, 1.0, pg))

    # youth panel
    py = ease_out(prog(lt, 6.0, 6.8))
    if py > 0:
        yo = (1 - py) * 80 + 45
        d.line((x0, 985 + yo, x0 + full * py, 985 + yo), fill=rgba(GOLD, py), width=3)
        frac = FACTS["youth_voted_r1_m"] / FACTS["youth_eligible_m"]
        rp = ease_out(prog(lt, 7.6, 9.4))
        cx, cy = 210, 1150 + yo
        ring(d, cx, cy, 118, 28, frac * rp, GOLD)
        d.text((cx, cy - 10), f"{fmt_num(round(frac * 100 * rp, 1), lang, 1)}%", font=font("anton", 58),
               fill=rgba(WHITE, py), anchor="mm")
        d.text((cx, cy + 42), "R1", font=font("oswald", 26, 500), fill=rgba(GREY, py), anchor="mm")
        tx = 380
        d.text((tx, 1010 + yo), T["s1_youth_head"], font=font("oswald", 36, 650), fill=rgba(GOLD, py))
        cnt = FACTS["youth_eligible_m"] * ease_out(prog(lt, 6.2, 7.6))
        d.text((tx - 4, 1050 + yo), f"{fmt_num(round(cnt, 1), lang, 1)}M", font=font("anton", 128),
               fill=rgba(WHITE, py))
        d.text((tx, 1212 + yo), T["s1_youth_sub"], font=font("oswald", 30, 500), fill=rgba(GREY, py))
        pv = prog(lt, 8.0, 8.5)
        vt = T["s1_youth_voted"].format(v=fmt_num(FACTS["youth_voted_r1_m"], lang))
        d.rectangle((tx, 1256 + yo, tx + 16, 1300 + yo), fill=rgba(GOLD, pv))
        d.text((tx + 28, 1278 + yo), vt, font=font("oswald", 34, 650), fill=rgba(WHITE, pv), anchor="lm")


def scene2(layer, lt, lang):
    T = TEXT[lang]
    d = ImageDraw.Draw(layer, "RGBA")
    kicker(layer, d, T["s2_kicker"], lt)

    # Phase A: kinetic typography
    out = ease_out(prog(lt, 4.3, 4.8))
    if out < 1:
        cols = [WHITE, CRIMSON, WHITE, GOLD]
        for i, (w, sub) in enumerate(zip(T["s2_words"], T["s2_words_sub"])):
            ts = 0.25 + i * 0.8
            p = prog(lt, ts, ts + 0.28)
            if p <= 0:
                continue
            y = 445 + i * 185
            sz = fit_size(w, "anton", 140, 900)
            sc = lerp(1.7, 1.0, ease_out(p))
            shake = (math.sin(lt * 90) * 6 * (1 - prog(lt, ts + 0.28, ts + 0.5))) if p >= 1 else 0
            x = 90 - out * 1100 + shake
            place(layer, text_img(sub, "oswald", 28, GREY, 500), x + 4, y - 8, "lb", alpha=p * (1 - out))
            place(layer, text_img(w, "anton", sz, cols[i], shadow=8), x, y, "lt",
                  alpha=clamp(p * 1.4) * (1 - out), scale=sc)
        pt = ease_back(prog(lt, 3.4, 3.9))
        if pt > 0:
            _transit_badge(layer, d, T, 1235, pt, 1 - out, big=True)

    # Phase B: data
    if lt >= 4.5:
        a = ease_out(prog(lt, 4.5, 5.1))
        # waffle: each square = 1% of municipalities
        x0, y0, cell, gap = 90, 500, 30, 5
        d.text((x0, 440), T["s2_waffle_head"], font=font("oswald", 34, 650), fill=rgba(WHITE, a))
        lit = int(FACTS["municipalities_abst_down_pct"] * ease_out(prog(lt, 5.0, 7.4)))
        for k in range(100):
            r, c = divmod(k, 10)
            cx, cy = x0 + c * (cell + gap), y0 + (9 - r) * (cell + gap)
            col = CRIMSON if k < lit else TRACK
            d.rectangle((cx, cy, cx + cell, cy + cell), fill=rgba(col, a))
        pct_img = text_img(f"{FACTS['municipalities_abst_down_pct']}%", "anton", 110, GOLD, shadow=5)
        place(layer, text_img(f"{lit}%", "anton", 110, GOLD, shadow=5), x0 - 4, 850, "lt", alpha=a)
        sx = x0 + pct_img.width + 6
        sub = T["s2_waffle_sub"]
        d.text((sx, 915), sub, font=font("oswald", fit_size(sub, "oswald", 30, 525 - sx, 650), 650),
               fill=rgba(WHITE, a), anchor="lm")
        d.text((x0, 985), T["s2_waffle_note"], font=font("oswald", 22, 400), fill=rgba(GREY, a * 0.8))

        # matplotlib slope chart
        cp = prog(lt, 6.0, 9.0)
        step = int(round(cp * 40))
        d.text((560, 440), T["s2_chart_head"], font=font("oswald", 34, 650), fill=rgba(WHITE, a))
        place(layer, abstention_chart(step, lang), 535, 490, "lt", alpha=a)

        # turnout counter
        pc = ease_out(prog(lt, 8.6, 10.2))
        if pc > 0:
            d.line((90, 1040, 990, 1040), fill=rgba(GOLD, pc), width=3)
            val = f"{fmt_num(round(FACTS['r2_turnout_m'] * pc, 1), lang, 1)}M"
            place(layer, text_img(val, "anton", 132, WHITE, shadow=6), 90, 1050, "lt",
                  alpha=clamp(pc * 2), scale=lerp(1.15, 1.0, pc))
            d.text((560, 1125), T["s2_turnout"], font=font("oswald",
                   fit_size(T["s2_turnout"], "oswald", 34, 430, 650), 650), fill=rgba(GOLD, pc), anchor="lm")
        pt = ease_out(prog(lt, 10.0, 10.5))
        if pt > 0:
            _transit_badge(layer, d, T, 1285, pt, 1.0, big=False)


def _transit_badge(layer, d, T, y, p, alpha, big):
    txt = T["s2_transit"]
    size = fit_size(txt, "anton", 46 if big else 36, 760)
    ti = text_img(txt, "anton", size, CHARCOAL)
    icon = bus_icon(int(ti.height * 0.95), CHARCOAL)
    bw = ti.width + icon.width + 60
    bh = max(ti.height, icon.height) + 22
    badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.rectangle((0, 0, bw - 1, bh - 1), fill=GOLD)
    badge.alpha_composite(icon, (18, (bh - icon.height) // 2))
    badge.alpha_composite(ti, (icon.width + 36, (bh - ti.height) // 2))
    place(layer, badge, W // 2, y, "mm", alpha=alpha * clamp(p), scale=max(0.01, p) if big else 1.0)


def scene3(layer, lt, lang):
    T = TEXT[lang]
    d = ImageDraw.Draw(layer, "RGBA")
    kicker(layer, d, T["s3_kicker"], lt)
    lx, ys = 150, [470, 680, 890]
    lp = ease_in_out(prog(lt, 0.4, 5.6))
    ytop, ybot = ys[0], ys[-1]
    d.line((lx, ytop, lx, ybot), fill=rgba(TRACK), width=8)
    d.line((lx, ytop, lx, ytop + (ybot - ytop) * lp), fill=rgba(GOLD), width=8)
    node_cols = [GREY, GOLD, CRIMSON]
    dim = 1 - 0.55 * prog(lt, 10.0, 10.6)
    for i, (date, title, detail) in enumerate(T["s3_nodes"]):
        reach = (ys[i] - ytop) / (ybot - ytop)
        pn = prog(lt, 0.4 + 5.2 * reach, 0.8 + 5.2 * reach)
        if pn <= 0:
            continue
        y = ys[i]
        r = 22 if i < 2 else 30
        if i == 2:
            pulse = (math.sin(lt * 6) + 1) / 2
            rr = r + 10 + 18 * pulse
            d.ellipse((lx - rr, y - rr, lx + rr, y + rr), outline=rgba(CRIMSON, 0.5 * pn), width=4)
        rs = r * ease_back(pn)
        d.ellipse((lx - rs, y - rs, lx + rs, y + rs), fill=rgba(node_cols[i], pn), outline=rgba(WHITE, pn),
                  width=4)
        tx = 215 + (1 - ease_out(pn)) * 60
        a = pn * (dim if i < 2 else 1)
        d.text((tx, y - 64), date, font=font("anton", 60), fill=rgba(GOLD if i else WHITE, a))
        d.text((tx, y + 14), title, font=font("oswald", 40, 700), fill=rgba(WHITE, a))
        dsz = fit_size(detail, "oswald", 30, 800, 500)
        d.text((tx, y + 66), detail, font=font("oswald", dsz, 500), fill=rgba(GREY if i < 2 else WHITE, a))

    # rank flip: 2ND -> 1ST next to the runoff node
    pf = ease_back(prog(lt, 6.0, 6.5))
    if pf > 0:
        badge = text_img(T["s3_term"], "anton", 54, CHARCOAL)
        b = Image.new("RGBA", (badge.width + 36, badge.height + 16), GOLD + (255,))
        b.alpha_composite(badge, (18, 8))
        place(layer, b, 975, 838, "rm", alpha=clamp(pf), scale=max(0.01, pf), rotate=6)

    # historic stamp
    ps = prog(lt, 7.0, 7.35)
    if ps > 0:
        s1 = T["s3_stamp_1"]
        ti = text_img(s1, "anton", fit_size(s1, "anton", 100, 820), WHITE)
        st = Image.new("RGBA", (ti.width + 70, ti.height + 40), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rectangle((0, 0, st.width - 1, st.height - 1), fill=CRIMSON, outline=WHITE, width=6)
        sd.rectangle((12, 12, st.width - 13, st.height - 13), outline=(255, 255, 255, 120), width=2)
        st.alpha_composite(ti, (35, 20))
        place(layer, st, W // 2, 1110, "mm", alpha=clamp(ps * 2), scale=lerp(2.2, 1.0, ease_out(ps)),
              rotate=-4)
        s2 = T["s3_stamp_2"]
        p2 = prog(lt, 7.6, 8.1)
        place(layer, text_img(s2, "oswald", fit_size(s2, "oswald", 32, 900, 650), GOLD, 650), W // 2,
              1200, "mt", alpha=p2)

    pq = ease_out(prog(lt, 10.0, 10.6))
    if pq > 0:
        q = "“" + T["s3_quote"] + "”"
        qs = fit_size(q, "oswald", 34, 860, 700)
        y = 1262
        d.rectangle((60, y, 60 + 960 * pq, y + 66), fill=rgba(CHARCOAL_2, 0.95))
        d.rectangle((60, y, 72, y + 66), fill=rgba(CRIMSON))
        d.text((92, y + 33), q, font=font("oswald", qs, 700), fill=rgba(WHITE, pq), anchor="lm")


def scene4(layer, lt, lang):
    T = TEXT[lang]
    d = ImageDraw.Draw(layer, "RGBA")
    kicker(layer, d, T["s4_kicker"], lt)
    final = ease_out(prog(lt, 8.7, 9.3))
    body = 1 - 0.85 * final

    p = ease_out(prog(lt, 0.2, 0.7))
    d.text((90, 440), T["s4_title"], font=font("oswald", 52, 600), fill=rgba(WHITE, p * body))
    t2 = T["s4_title_2"]
    place(layer, text_img(t2, "anton", fit_size(t2, "anton", 128, 900), GOLD, shadow=6), 86, 505, "lt",
          alpha=p * body, scale=lerp(1.1, 1.0, p))
    pl = ease_out(prog(lt, 0.6, 1.6))
    for k in range(0, int(900 * pl), 44):
        d.rectangle((90 + k, 680, 90 + k + 26, 688), fill=rgba(WHITE, body))

    ph = prog(lt, 1.0, 1.4)
    ca, cb = T["s4_col_a"], T["s4_col_b"]
    d.text((90, 720), ca, font=font("oswald", fit_size(ca, "oswald", 30, 420, 650), 650),
           fill=rgba(GREY, ph * body))
    d.text((560, 720), cb, font=font("oswald", fit_size(cb, "oswald", 30, 420, 650), 650),
           fill=rgba(CRIMSON, ph * body))
    for i, (old, new) in enumerate(T["s4_rows"]):
        ts = 1.4 + i * 1.25
        pa = ease_out(prog(lt, ts, ts + 0.35))
        if pa <= 0:
            continue
        y = 775 + i * 118
        xo = (1 - pa) * -500
        d.rectangle((90 + xo, y, 520 + xo, y + 100), fill=rgba(CHARCOAL_2, 0.95 * body))
        osz = fit_size(old, "oswald", 32, 390, 500)
        d.text((110 + xo, y + 50), old, font=font("oswald", osz, 500), fill=rgba(GREY, pa * body), anchor="lm")
        pk = ease_out(prog(lt, ts + 0.45, ts + 0.75))
        if pk > 0:
            tw = font("oswald", osz, 500).getlength(old)
            d.line((106 + xo, y + 52, 106 + xo + (tw + 8) * pk, y + 52), fill=rgba(CRIMSON, body), width=5)
        pb = ease_back(prog(lt, ts + 0.55, ts + 0.95))
        if pb > 0:
            card = Image.new("RGBA", (430, 100), CRIMSON + (255,))
            cd = ImageDraw.Draw(card)
            cd.rectangle((0, 0, 10, 100), fill=GOLD)
            nsz = fit_size(new, "anton", 40, 390)
            cd.text((26, 50), new, font=font("anton", nsz), fill=WHITE, anchor="lm")
            place(layer, card, 560 + 215, y + 50, "mm", alpha=clamp(pb) * body, scale=max(0.01, pb))
        # arrow between columns
        if pk > 0:
            d.polygon([(528, y + 38), (552, y + 50), (528, y + 62)], fill=rgba(GOLD, pk * body))

    if final > 0:
        d.rectangle((0, 330, W, 1340), fill=rgba(CHARCOAL, 0.55 * final))
        f1, f2 = T["s4_final_1"], T["s4_final_2"]
        place(layer, text_img(f1, "anton", fit_size(f1, "anton", 150, 940), WHITE, shadow=8), W // 2, 720,
              "mm", alpha=final, scale=lerp(1.3, 1.0, final))
        pf2 = ease_out(prog(lt, 9.2, 9.7))
        bar = text_img(f2, "anton", fit_size(f2, "anton", 76, 880), CHARCOAL)
        slab = Image.new("RGBA", (bar.width + 60, bar.height + 26), GOLD + (255,))
        slab.alpha_composite(bar, (30, 13))
        place(layer, slab, W // 2, 870, "mt", alpha=pf2, scale=max(0.01, lerp(0.6, 1.0, pf2)))
        pso = prog(lt, 10.0, 10.6)
        so = T["sign_off"]
        d.line((W // 2 - 300 * pso, 1080, W // 2 + 300 * pso, 1080), fill=rgba(CRIMSON), width=4)
        d.text((W // 2, 1130), so, font=font("oswald", fit_size(so, "oswald", 36, 900, 650), 650),
               fill=rgba(WHITE, pso), anchor="mm")


SCENE_FUNCS = [scene1, scene2, scene3, scene4]


# --------------------------------------------------------------------------- HUD (always 100% opacity)
class Hud:
    def __init__(self, lang, fps):
        self.lang, self.fps = lang, fps
        T = TEXT[lang]
        self.T = T
        tick = T["ticker"] * 3
        f = font("oswald", 32, 600)
        tw = int(f.getlength(tick)) + 20
        self.ticker = Image.new("RGBA", (tw, 60), (0, 0, 0, 0))
        ImageDraw.Draw(self.ticker).text((0, 30), tick, font=f, fill=WHITE, anchor="lm")
        self.tick_period = f.getlength(T["ticker"])

    def draw(self, layer, t, duration):
        T = self.T
        d = ImageDraw.Draw(layer, "RGBA")
        # progress bar
        d.rectangle((0, 0, W, 8), fill=rgba(BLACK, 0.6))
        d.rectangle((0, 0, W * t / duration, 8), fill=rgba(CRIMSON))
        # banner
        p = ease_out(prog(t, 0.0, 0.5))
        xo = -(1 - p) * W
        d.rectangle((xo, 96, xo + W, 186), fill=rgba(CRIMSON))
        d.rectangle((xo, 186, xo + W, 272), fill=rgba(BLACK, 0.92))
        d.rectangle((xo, 272, xo + W, 278), fill=rgba(GOLD))
        live_w = 34 + font("anton", 40).getlength(T["live"]) + 40
        d.rectangle((xo, 96, xo + live_w + 20, 186), fill=rgba(WHITE))
        blink = 1.0 if int(t * 2) % 2 == 0 else 0.25
        d.ellipse((xo + 22, 128, xo + 48, 154), fill=rgba(CRIMSON, blink))
        d.text((xo + 60, 141), T["live"], font=font("anton", 40), fill=CRIMSON, anchor="lm")
        b1 = T["banner_1"]
        bx = xo + live_w + 44
        d.text((bx, 141), b1, font=font("anton", fit_size(b1, "anton", 50, W - bx + xo - 30)), fill=WHITE,
               anchor="lm")
        b2 = T["banner_2"]
        d.text((xo + 30, 229), b2, font=font("anton", fit_size(b2, "anton", 62, W - 60)), fill=GOLD,
               anchor="lm")
        d.text((W - 30 + xo, 300), T["channel"] + f"   {int(t) // 60:02d}:{int(t) % 60:02d}",
               font=font("oswald", 24, 500), fill=rgba(GREY, p), anchor="rm")
        # ticker
        ty = 1572
        d.rectangle((0, ty, W, ty + 58), fill=rgba(BLACK, 0.85))
        off = int((t * 170) % self.tick_period)
        strip = self.ticker.crop((off, 0, off + W, 60))
        layer.alpha_composite(strip, (0, ty - 1))
        tag = "GN 1.0"
        tf = font("anton", 34)
        tgw = tf.getlength(tag) + 36
        d.rectangle((0, ty, tgw, ty + 58), fill=rgba(CRIMSON))
        d.text((18, ty + 29), tag, font=tf, fill=WHITE, anchor="lm")


# --------------------------------------------------------------------------- captions
def group_captions(words, max_words=3, max_chars=20, max_gap=0.18):
    chunks, cur = [], []
    for w in words:
        if cur:
            text_len = sum(len(x["text"]) + 1 for x in cur) + len(w["text"])
            if (len(cur) >= max_words or text_len > max_chars or w["start"] - cur[-1]["end"] > max_gap
                    or w["scene"] != cur[-1]["scene"]):
                chunks.append(cur)
                cur = []
        cur.append(w)
    if cur:
        chunks.append(cur)
    out = []
    for i, c in enumerate(chunks):
        start = c[0]["start"]
        end = c[-1]["end"] + 0.25
        if i + 1 < len(chunks):
            end = min(end, chunks[i + 1][0]["start"])
        out.append({"start": start, "end": end, "words": c})
    return out


class Captions:
    Y = 1440
    MAX_W = 860

    def __init__(self, words):
        self.chunks = group_captions(words)

    def draw(self, layer, t):
        ch = next((c for c in self.chunks if c["start"] <= t < c["end"]), None)
        if ch is None:
            return
        words = [w["text"].upper() for w in ch["words"]]
        active = max([i for i, w in enumerate(ch["words"]) if w["start"] <= t] or [0])
        size = 86
        f = font("anton", size)
        space = f.getlength(" ")
        while size > 40 and sum(f.getlength(w) for w in words) + space * (len(words) - 1) > self.MAX_W:
            size -= 4
            f = font("anton", size)
            space = f.getlength(" ")
        widths = [f.getlength(w) for w in words]
        total = sum(widths) + space * (len(words) - 1)
        img = Image.new("RGBA", (int(total) + 60, size + 70), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        x = 30
        cy = img.height // 2
        for i, (w, ww) in enumerate(zip(words, widths)):
            if i == active:
                d.rectangle((x - 12, cy - size * 0.62, x + ww + 12, cy + size * 0.62), fill=CRIMSON)
            d.text((x, cy), w, font=f, fill=GOLD if i == active else WHITE, anchor="lm",
                   stroke_width=6, stroke_fill=BLACK)
            x += ww + space
        pop = ease_out(prog(t, ch["start"], ch["start"] + 0.12))
        place(layer, img, W // 2, self.Y, "mm", scale=lerp(1.12, 1.0, pop))


# --------------------------------------------------------------------------- compositor
class Compositor:
    def __init__(self, lang, fps, words, duration, broll_reader=None, overlay_opacity=0.85):
        self.lang, self.fps, self.duration = lang, fps, duration
        self.plate = background_plate()
        self.vig = vignette_mask()
        self.grain = grain_textures()
        self.hud = Hud(lang, fps)
        self.caps = Captions(words)
        self.broll = broll_reader
        self.opacity = overlay_opacity if broll_reader else 1.0

    def frame(self, i):
        t = i / self.fps
        if self.broll is not None:
            # darken B-roll and tint it toward the charcoal plate so overlays stay legible
            base = ((self.broll.read().astype(np.uint16) * 140 + self.plate.astype(np.uint16) * 60) >> 8
                    ).astype(np.uint8)
        else:
            base = self.plate
        img = Image.fromarray(base).convert("RGBA")

        # scene layer (data overlays + kinetic type) at overlay opacity
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        for k, (s0, s1) in enumerate(SCENES):
            if s0 - 1e-6 <= t < s1 + (1e-6 if k == len(SCENES) - 1 else 0):
                SCENE_FUNCS[k](layer, t - s0, self.lang)
                fade = min(prog(t, s0, s0 + 0.2) if k else 1.0, 1 - prog(t, s1 - 0.18, s1) if k < 3 else 1.0)
                a = self.opacity * fade
                if a < 0.999:
                    layer = with_alpha(layer, a)
        img.alpha_composite(layer)

        hud = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        self.hud.draw(hud, t, self.duration)
        self.caps.draw(hud, t)
        img.alpha_composite(hud)

        arr = np.asarray(img.convert("RGB"))
        arr = self._transition(arr, t)
        # grade: vignette + scanlines, film grain, gentle flicker
        f = arr.astype(np.uint16) * self.vig >> 8
        f = f.astype(np.int16) + self.grain[i % len(self.grain)]
        flick = 1.0 + 0.025 * math.sin(i * 1.7) * math.sin(i * 0.31)
        if abs(flick - 1) > 0.002:
            f = (f * flick).astype(np.int16)
        return np.clip(f, 0, 255).astype(np.uint8)

    def _transition(self, arr, t):
        for s0, _ in SCENES[1:]:
            dt = t - s0
            if -0.22 <= dt <= 0.22:
                p = (dt + 0.22) / 0.44
                arr = arr.copy()
                # crimson diagonal sweep
                x = int(lerp(-600, W + 600, p))
                yy = np.arange(H)[:, None]
                xx = np.arange(W)[None, :]
                band = np.abs((xx + yy * 0.35) - x - H * 0.17) < 140
                arr[band] = (arr[band] * 0.25 + np.array(CRIMSON) * 0.75).astype(np.uint8)
                # RGB split glitch
                sh = int(18 * (1 - abs(dt) / 0.22))
                if sh:
                    arr[..., 0] = np.roll(arr[..., 0], sh, axis=1)
                    arr[..., 2] = np.roll(arr[..., 2], -sh, axis=1)
        return arr
