"""Static matplotlib layers: Mayon height-profile chart and Albay danger-zone map.

Each builder returns a PIL RGBA image plus a function that maps data
coordinates to pixel coordinates inside that image, so the per-frame Pillow
renderer can animate plume particles, rings and corridors precisely on top.
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LightSource, LinearSegmentedColormap  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402
from PIL import Image  # noqa: E402
from scipy.ndimage import gaussian_filter  # noqa: E402

from . import config as C  # noqa: E402

SUMMIT_M = 2463.0


def _setup_fonts():
    for kind in ("bold", "mono", "semi"):
        p = C.font_path(kind)
        if p:
            try:
                font_manager.fontManager.addfont(p)
            except Exception:
                pass
    fam = []
    p = C.font_path("bold")
    if p:
        fam.append(font_manager.FontProperties(fname=p).get_name())
    plt.rcParams["font.family"] = fam + ["DejaVu Sans"]


def _fig_to_image(fig) -> Image.Image:
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba()).copy()
    return Image.fromarray(buf, "RGBA")


def cone_profile(x_km):
    """Mayon's near-perfect concave stratovolcano profile (metres)."""
    r = np.maximum(np.abs(x_km) - 0.12, 0.0)
    return SUMMIT_M * np.exp(-(r / 3.0) ** 0.9)


# ----------------------------------------------------- scene 1: profile ---
def volcano_chart(ui: dict, size=(1000, 720)):
    _setup_fonts()
    w, h = size
    dpi = 100
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    fig.patch.set_alpha(0.0)
    ax = fig.add_axes([0.105, 0.12, 0.80, 0.86])
    ax.patch.set_alpha(0.0)
    xlim, ylim = (-12, 12), (0, 6500)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)

    x = np.linspace(*xlim, 1600)
    y = cone_profile(x)
    # flank shading: lit west flank, shadowed east flank
    ax.fill_between(x, 0, y, color=C.hexc((40, 40, 45)), lw=0, zorder=2)
    ax.fill_between(x[x <= 0], 0, y[x <= 0], color=C.hexc((58, 56, 58)), lw=0, zorder=2)
    # strata lines for texture
    for k, frac in enumerate(np.linspace(0.12, 0.9, 7)):
        ax.plot(x, y * frac, color="#ffffff", alpha=0.035 + 0.01 * (k % 2), lw=1, zorder=3)
    ax.plot(x, y, color=C.hexc(C.ORANGE), lw=3.2, zorder=4, solid_capstyle="round")
    ax.plot(x, y, color=C.hexc(C.ORANGE), lw=9, alpha=0.18, zorder=3)

    # 6-km Permanent Danger Zone band on the ground
    ax.fill_between([-6, 6], 0, 140, color=C.hexc(C.ORANGE), alpha=0.55, lw=0, zorder=5)
    for xs in (-6, 6):
        ax.plot([xs, xs], [0, cone_profile(np.array([xs]))[0] + 900], ls=(0, (4, 3)),
                color=C.hexc(C.SULFUR), lw=2, alpha=0.9, zorder=5)
    ax.text(0, 330, ui["chart_pdz"], ha="center", va="center", color=C.hexc(C.ASH),
            fontsize=13, fontweight="bold", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", fc=C.hexc(C.SULFUR), ec="none"))
    ax.annotate(ui["chart_summit"], xy=(-0.25, SUMMIT_M), xytext=(-8.6, 3350),
                color=C.hexc(C.WHITE), fontsize=15, fontweight="bold", zorder=6,
                arrowprops=dict(arrowstyle="-", color=C.hexc(C.GRAY), lw=1.5))

    # grid & axes
    ax.set_yticks(range(0, 6001, 1000))
    ax.set_yticklabels([f"{v:,} m" if v else "0" for v in range(0, 6001, 1000)])
    ax.set_xticks(range(-12, 13, 3))
    ax.set_xticklabels([str(abs(v)) for v in range(-12, 13, 3)])
    ax.grid(axis="y", color="#ffffff", alpha=0.09, lw=1)
    ax.grid(axis="x", color="#ffffff", alpha=0.04, lw=1)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(C.hexc(C.GRAY_DIM))
    ax.tick_params(colors=C.hexc(C.GRAY), labelsize=13, length=0, pad=6)
    ax.set_xlabel(ui["chart_x"], color=C.hexc(C.GRAY), fontsize=13, labelpad=8)

    sec = ax.secondary_yaxis("right", functions=(lambda m: m * 3.28084, lambda f: f / 3.28084))
    sec.set_yticks(range(0, 20001, 5000))
    sec.set_yticklabels([f"{v // 1000}k ft" if v else "0" for v in range(0, 20001, 5000)])
    sec.tick_params(colors=C.hexc(C.GRAY_DIM), labelsize=12, length=0, pad=6)
    sec.spines["right"].set_visible(False)

    img = _fig_to_image(fig)
    # data → pixel mapping (matplotlib display origin is bottom-left)
    p00 = ax.transData.transform((0, 0))
    p11 = ax.transData.transform((1, 1000))
    plt.close(fig)
    sx, sy = p11[0] - p00[0], (p11[1] - p00[1]) / 1000.0

    def to_px(xkm, ym):
        return (p00[0] + xkm * sx, h - (p00[1] + ym * sy))

    return img, to_px


# --------------------------------------------------------- scene 2: map ---
MAYON_LATLON = (13.2575, 123.6856)
KM_PER_DEG_LAT = 110.6
KM_PER_DEG_LON = 108.4  # at ~13.25°N

# extent in km relative to the Mayon crater (x east, y north)
MAP_X0, MAP_X1 = -20.0, 16.0
MAP_Y0 = -14.6


def ll_to_km(lat, lon):
    return ((lon - MAYON_LATLON[1]) * KM_PER_DEG_LON, (lat - MAYON_LATLON[0]) * KM_PER_DEG_LAT)


TOWNS = {   # approximate town-centre coordinates
    "tabaco": ll_to_km(13.3586, 123.7337),
    "camalig": ll_to_km(13.1817, 123.6554),
    "ligao": ll_to_km(13.2402, 123.5370),
}
LEGAZPI = ll_to_km(13.1391, 123.7353)

# simplified Albay Gulf / Tabaco Bay coastline (south → north)
_COAST_LL = [(13.00, 123.80), (13.08, 123.775), (13.12, 123.762), (13.145, 123.757),
             (13.17, 123.772), (13.205, 123.781), (13.235, 123.778), (13.265, 123.800),
             (13.290, 123.792), (13.305, 123.768), (13.325, 123.742), (13.345, 123.738),
             (13.365, 123.737), (13.385, 123.748), (13.405, 123.772), (13.46, 123.80)]
COAST_KM = [ll_to_km(a, b) for a, b in _COAST_LL]


def albay_map(ui: dict, size=(1100, 858)):
    """Satellite-style shaded-relief vector map; returns (img, km→px, extent)."""
    _setup_fonts()
    w, h = size
    span_x = MAP_X1 - MAP_X0
    span_y = span_x * h / w
    y0, y1 = MAP_Y0, MAP_Y0 + span_y
    nx, ny = w, h
    xs = np.linspace(MAP_X0, MAP_X1, nx)
    ys = np.linspace(y0, y1, ny)
    X, Y = np.meshgrid(xs, ys)
    R = np.hypot(X, Y)

    rng = np.random.default_rng(42)
    elev = cone_profile(R)
    # neighbouring massifs (approximate) – Masaraga (NW) and Malinao (N)
    for (lat, lon, hgt, rad) in [(13.317, 123.596, 1328, 3.2), (13.42, 123.60, 1548, 4.0),
                                 (13.10, 123.55, 600, 6.0)]:
        cx, cy = ll_to_km(lat, lon)
        elev += hgt * np.exp(-((np.hypot(X - cx, Y - cy)) / rad) ** 1.4)
    noise = sum(gaussian_filter(rng.standard_normal((ny, nx)), s) * a
                for s, a in [(40, 1400), (14, 520), (5, 80), (1.5, 12)])
    elev += noise
    # radial lahar gullies on Mayon's flanks
    ang = np.arctan2(Y, X) + gaussian_filter(rng.standard_normal((ny, nx)), 25) * 6.0
    gully = (np.abs(np.sin(ang * 14)) ** 6) * np.exp(-((R - 3.5) / 2.8) ** 2) * 60
    elev -= gully

    coast_poly = COAST_KM + [(60, y1 + 60), (60, y0 - 60)]
    sea = MPath(coast_poly).contains_points(np.c_[X.ravel(), Y.ravel()]).reshape(ny, nx)
    elev = np.where(sea, -50, np.maximum(elev, 5))

    cmap = LinearSegmentedColormap.from_list("ashsat", [
        (0.00, "#1b2119"), (0.10, "#273024"), (0.25, "#353a2c"), (0.45, "#4a4638"),
        (0.70, "#5d5850"), (1.00, "#8a8682")])
    ls = LightSource(azdeg=315, altdeg=35)
    land = np.clip(elev, 0, 2600)
    px_m = span_x * 1000.0 / nx
    rgb = ls.shade(land, cmap=cmap, blend_mode="overlay", vert_exag=2.2, dx=px_m, dy=px_m,
                   vmin=0, vmax=2600)[..., :3]
    # volcanic deposit tint (fresh ash, grey) on the upper cone
    ash_mask = np.clip((cone_profile(R) - 700) / 1200, 0, 1)[..., None] * 0.35
    rgb = rgb * (1 - ash_mask) + np.array([0.42, 0.41, 0.40]) * ash_mask
    sea_rgb = np.array([0.05, 0.075, 0.09]) + gaussian_filter(rng.standard_normal((ny, nx)), 3)[..., None] * 0.01
    rgb = np.where(sea[..., None], sea_rgb, rgb)
    rgb = np.clip(rgb * 0.82, 0, 1)

    dpi = 100
    fig = plt.figure(figsize=(w / dpi, h / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.imshow(rgb, extent=[MAP_X0, MAP_X1, y0, y1], origin="lower", interpolation="bilinear")
    cx, cy = zip(*COAST_KM)
    ax.plot(cx, cy, color="#c9d3d6", lw=1.6, alpha=0.55)
    # graticule every 0.05°
    for lat in np.arange(13.10, 13.40, 0.05):
        _, yk = ll_to_km(lat, MAYON_LATLON[1])
        ax.axhline(yk, color="#ffffff", alpha=0.07, lw=1)
        ax.text(MAP_X0 + 0.3, yk + 0.25, f"{lat:.2f}°N", color="#ffffff", alpha=0.35, fontsize=9)
    for lon in np.arange(123.50, 123.85, 0.05):
        xk, _ = ll_to_km(MAYON_LATLON[0], lon)
        ax.axvline(xk, color="#ffffff", alpha=0.07, lw=1)
        ax.text(xk + 0.2, y0 + 0.3, f"{lon:.2f}°E", color="#ffffff", alpha=0.35, fontsize=9)
    ax.set_xlim(MAP_X0, MAP_X1)
    ax.set_ylim(y0, y1)
    ax.axis("off")
    img = _fig_to_image(fig)
    plt.close(fig)

    def to_px(xkm, ykm):
        return ((xkm - MAP_X0) / span_x * w, (y1 - ykm) / span_y * h)

    return img, to_px, (MAP_X0, MAP_X1, y0, y1)
