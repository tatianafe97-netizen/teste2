"""Map rendering with matplotlib: orthographic funding map + Ukraine radar scope."""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon as MplPolygon, Circle
from PIL import Image

from .config import (DATA_DIR, NAVY_DEEP, PANEL, CYAN, NATO_BLUE, NATO_LIGHT,
                     AMBER, GREY, hexc)

# Orthographic view centred over the North Atlantic so Canada, Europe and
# Ukraine sit on one curved horizon.
LAT0, LON0 = 50.0, -24.0
MAP_W, MAP_H = 980, 480
X0, X1 = -0.74, 0.74
_YSPAN = (X1 - X0) * MAP_H / MAP_W
Y0, Y1 = -0.19, -0.19 + _YSPAN

CITIES = {
    "CA": ("Ottawa", 45.42, -75.70),
    "DE": ("Berlin", 52.52, 13.40),
    "NO": ("Oslo", 59.91, 10.75),
    "EU": ("Brussels", 50.85, 4.35),
    "US": ("Washington", 38.90, -77.04),
    "UA": ("Kyiv", 50.45, 30.52),
}
FUNDER_ISO = {"CAN", "DEU", "NOR"}
EU_MEMBERS = {"AUT", "BEL", "BGR", "HRV", "CYP", "CZE", "DNK", "EST", "FIN", "FRA",
              "GRC", "HUN", "IRL", "ITA", "LVA", "LTU", "LUX", "MLT", "NLD", "POL",
              "PRT", "ROU", "SVK", "SVN", "ESP", "SWE"}


@lru_cache(maxsize=1)
def geodata() -> dict:
    p = DATA_DIR / "geodata.json"
    if not p.exists():
        return {"world": {}, "region": {}}
    return json.loads(p.read_text())


def ortho(lat, lon):
    """Orthographic projection; far-side points are pushed onto the limb."""
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    la0, lo0 = np.radians(LAT0), np.radians(LON0)
    cosc = np.sin(la0) * np.sin(lat) + np.cos(la0) * np.cos(lat) * np.cos(lon - lo0)
    x = np.cos(lat) * np.sin(lon - lo0)
    y = np.cos(la0) * np.sin(lat) - np.sin(la0) * np.cos(lat) * np.cos(lon - lo0)
    back = cosc < 0
    if np.any(back):
        r = np.hypot(x, y) + 1e-9
        x = np.where(back, x / r, x)
        y = np.where(back, y / r, y)
    return x, y


def map_px(lat: float, lon: float) -> tuple[float, float]:
    x, y = ortho(lat, lon)
    return (float((x - X0) / (X1 - X0) * MAP_W), float((Y1 - y) / (Y1 - Y0) * MAP_H))


def _fig(w: int, h: int):
    fig = plt.figure(figsize=(w / 100, h / 100), dpi=100)
    fig.patch.set_alpha(0)
    return fig


def _to_image(fig) -> Image.Image:
    fig.canvas.draw()
    buf = np.asarray(fig.canvas.buffer_rgba()).copy()
    plt.close(fig)
    return Image.fromarray(buf, "RGBA")


def render_funding_map() -> Image.Image:
    """Static map plate (RGBA, MAP_W x MAP_H)."""
    fig = _fig(MAP_W, MAP_H)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(X0, X1)
    ax.set_ylim(Y0, Y1)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((X0, Y0), X1 - X0, Y1 - Y0, color=hexc(NAVY_DEEP), alpha=0.82, zorder=0))
    # globe disc + graticule
    ax.add_patch(Circle((0, 0), 1.0, color=hexc(PANEL), alpha=0.55, zorder=1))
    for lat in range(-80, 90, 10):
        lons = np.linspace(-180, 180, 721)
        x, y = ortho(np.full_like(lons, lat), lons)
        vis = _visible(np.full_like(lons, lat), lons)
        ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan), color=hexc(CYAN), lw=0.5, alpha=0.13, zorder=2)
    for lon in range(-180, 180, 10):
        lats = np.linspace(-90, 90, 361)
        x, y = ortho(lats, np.full_like(lats, lon))
        vis = _visible(lats, np.full_like(lats, lon))
        ax.plot(np.where(vis, x, np.nan), np.where(vis, y, np.nan), color=hexc(CYAN), lw=0.5, alpha=0.13, zorder=2)

    world = geodata()["world"]
    for code, rings in world.items():
        if code == "UKR":
            fc, ec, alpha, lw, z = hexc(AMBER), hexc(AMBER), 0.88, 1.2, 5
        elif code in FUNDER_ISO:
            fc, ec, alpha, lw, z = hexc(NATO_LIGHT), hexc(CYAN), 0.85, 1.0, 4
        elif code in EU_MEMBERS:
            fc, ec, alpha, lw, z = hexc(NATO_BLUE), hexc(CYAN), 0.75, 0.6, 3
        elif code == "USA":
            fc, ec, alpha, lw, z = "#26364f", hexc(GREY), 0.9, 0.6, 3
        else:
            fc, ec, alpha, lw, z = "#15294a", hexc(CYAN), 0.9, 0.4, 3
        for ring in rings:
            arr = np.array(ring)
            if not _visible(arr[:, 1], arr[:, 0]).any():
                continue
            x, y = ortho(arr[:, 1], arr[:, 0])
            ax.add_patch(MplPolygon(np.c_[x, y], closed=True, fc=fc, ec=ec, lw=lw,
                                    alpha=alpha, zorder=z, joinstyle="round"))
    return _to_image(fig)


def _visible(lat, lon) -> np.ndarray:
    lat, lon = np.radians(np.asarray(lat, float)), np.radians(np.asarray(lon, float))
    la0, lo0 = np.radians(LAT0), np.radians(LON0)
    return (np.sin(la0) * np.sin(lat) + np.cos(la0) * np.cos(lat) * np.cos(lon - lo0)) > 0


# ── Ukraine radar scope ─────────────────────────────────────────────────
SCOPE_LAT, SCOPE_LON = 48.6, 31.3
SCOPE_HALF = 8.2  # half-width in "equirectangular-km" degrees


def scope_xy(lat, lon):
    k = np.cos(np.radians(SCOPE_LAT))
    return (np.asarray(lon) - SCOPE_LON) * k, np.asarray(lat) - SCOPE_LAT


def scope_px(lat: float, lon: float, size: int) -> tuple[float, float]:
    x, y = scope_xy(lat, lon)
    return (float((x + SCOPE_HALF) / (2 * SCOPE_HALF) * size),
            float((SCOPE_HALF - y) / (2 * SCOPE_HALF) * size))


def render_scope_map(size: int) -> Image.Image:
    fig = _fig(size, size)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-SCOPE_HALF, SCOPE_HALF)
    ax.set_ylim(-SCOPE_HALF, SCOPE_HALF)
    ax.set_aspect("equal")
    ax.axis("off")
    clip = Circle((0, 0), SCOPE_HALF * 0.985, transform=ax.transData)
    bg = Circle((0, 0), SCOPE_HALF, color=hexc(NAVY_DEEP), alpha=0.92, zorder=0)
    ax.add_patch(bg)
    for code, rings in geodata()["region"].items():
        ukr = code == "UKR"
        for ring in rings:
            arr = np.array(ring)
            x, y = scope_xy(arr[:, 1], arr[:, 0])
            p = MplPolygon(np.c_[x, y], closed=True,
                           fc=hexc(AMBER) if ukr else "#11264a",
                           ec=hexc(AMBER) if ukr else hexc(CYAN),
                           lw=1.6 if ukr else 0.5, alpha=0.38 if ukr else 0.8,
                           zorder=3 if ukr else 2)
            p.set_clip_path(clip)
            ax.add_patch(p)
            if ukr:
                q = MplPolygon(np.c_[x, y], closed=True, fill=False, ec=hexc(AMBER), lw=2.0, zorder=4)
                q.set_clip_path(clip)
                ax.add_patch(q)
    for r in np.linspace(SCOPE_HALF / 4, SCOPE_HALF, 4):
        ax.add_patch(Circle((0, 0), r, fill=False, ec=hexc(CYAN), lw=0.9, alpha=0.35, zorder=5))
    for ang in range(0, 180, 30):
        a = np.radians(ang)
        ax.plot([-SCOPE_HALF * np.cos(a), SCOPE_HALF * np.cos(a)],
                [-SCOPE_HALF * np.sin(a), SCOPE_HALF * np.sin(a)],
                color=hexc(CYAN), lw=0.6, alpha=0.22, zorder=5)
    ax.add_patch(Circle((0, 0), SCOPE_HALF * 0.99, fill=False, ec=hexc(CYAN), lw=2.4, alpha=0.9, zorder=6))
    return _to_image(fig)
