"""Radar-style base map (matplotlib) for the mid-air U-turn scene.

Country outlines come from Natural Earth (public domain). They are downloaded
once into ``cache/``; if the download is impossible the map falls back to a
telemetry graticule so the pipeline still runs offline.
"""

from __future__ import annotations

import json
import math
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Polygon  # noqa: E402

NE_URLS = [
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson",
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson",
]

# geographic extent (lon_min, lon_max, lat_min, lat_max); linear lon/lat with
# the figure aspect chosen so that 1 deg lon ~= cos(34 deg) * 1 deg lat
EXTENT = (-26.0, 40.0, 11.0, 57.0)
MAP_W, MAP_H = 1000, 840

NAVY_OCEAN = "#061430"
LAND = "#11264d"
EDGE = "#2c4f86"
CRIMSON = "#dc143c"
GOLD = "#f2c14e"


def load_countries(cache_dir: Path):
    cache_dir.mkdir(parents=True, exist_ok=True)
    for url in NE_URLS:
        dst = cache_dir / url.rsplit("/", 1)[-1]
        if not dst.exists():
            try:
                print(f"  [map] downloading {dst.name} ...")
                with urllib.request.urlopen(url, timeout=30) as r:
                    dst.write_bytes(r.read())
            except Exception as exc:
                print(f"  [map] download failed: {exc}")
                continue
        try:
            return json.loads(dst.read_text(encoding="utf-8"))
        except Exception:
            dst.unlink(missing_ok=True)
    return None


def _rings(geom):
    if geom["type"] == "Polygon":
        yield from geom["coordinates"][:1]
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            yield poly[0]


def lonlat_to_px(lon: float, lat: float, x0: int = 0, y0: int = 0):
    lo0, lo1, la0, la1 = EXTENT
    return (x0 + (lon - lo0) / (lo1 - lo0) * MAP_W, y0 + (la1 - lat) / (la1 - la0) * MAP_H)


def render_basemap(path: Path, cache_dir: Path) -> Path:
    if path.exists():
        return path
    data = load_countries(cache_dir)
    fig = plt.figure(figsize=(MAP_W / 100, MAP_H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    lo0, lo1, la0, la1 = EXTENT
    ax.set_xlim(lo0, lo1)
    ax.set_ylim(la0, la1)
    ax.set_facecolor(NAVY_OCEAN)
    fig.patch.set_facecolor(NAVY_OCEAN)
    ax.axis("off")
    # graticule
    for lon in range(-20, 41, 5):
        ax.plot([lon, lon], [la0, la1], color="#1b3463", lw=0.6 if lon % 10 else 1.0, alpha=0.8, zorder=1)
    for lat in range(15, 57, 5):
        ax.plot([lo0, lo1], [lat, lat], color="#1b3463", lw=0.6 if lat % 10 else 1.0, alpha=0.8, zorder=1)
    if data:
        hi = {"POL": (CRIMSON, 0.55), "ESP": (GOLD, 0.18), "SEN": ("#7fa8ff", 0.35)}
        for feat in data["features"]:
            props = feat["properties"]
            iso = props.get("ADM0_A3") or props.get("ISO_A3")
            color, alpha = hi.get(iso, (LAND, 1.0))
            for ring in _rings(feat["geometry"]):
                xs = [p[0] for p in ring]
                ys = [p[1] for p in ring]
                if max(xs) < lo0 - 5 or min(xs) > lo1 + 5 or max(ys) < la0 - 5 or min(ys) > la1 + 5:
                    continue
                ax.add_patch(Polygon(list(zip(xs, ys)), closed=True, facecolor=LAND, edgecolor=EDGE, lw=0.8, zorder=2))
                if iso in hi:
                    ax.add_patch(Polygon(list(zip(xs, ys)), closed=True, facecolor=color, alpha=alpha,
                                         edgecolor=color, lw=1.6, zorder=3))
    # graticule labels (telemetry look)
    for lon in range(-20, 41, 10):
        ax.text(lon + 0.3, la0 + 0.5, f"{abs(lon)}°{'W' if lon < 0 else 'E'}", color="#4a6fa8", fontsize=9,
                family="DejaVu Sans Mono", zorder=4)
    for lat in range(20, 57, 10):
        ax.text(lo0 + 0.4, lat + 0.3, f"{lat}°N", color="#4a6fa8", fontsize=9, family="DejaVu Sans Mono", zorder=4)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=100, facecolor=NAVY_OCEAN)
    plt.close(fig)
    return path


# ------------------------------------------------------------ flight geometry
def _to_vec(lat, lon):
    la, lo = math.radians(lat), math.radians(lon)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def _to_ll(v):
    x, y, z = v
    return math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))


def great_circle(a, b, n=200):
    """Points (lat, lon) along the great circle from a to b."""
    va, vb = _to_vec(*a), _to_vec(*b)
    dot = max(-1.0, min(1.0, sum(p * q for p, q in zip(va, vb))))
    om = math.acos(dot)
    pts = []
    for i in range(n + 1):
        f = i / n
        s1 = math.sin((1 - f) * om) / math.sin(om)
        s2 = math.sin(f * om) / math.sin(om)
        pts.append(_to_ll(tuple(s1 * p + s2 * q for p, q in zip(va, vb))))
    return pts


def haversine_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def bearing(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    y = math.sin(lo2 - lo1) * math.cos(la2)
    x = math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(lo2 - lo1)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


WARSAW = (52.23, 21.01)
DAKAR = (14.69, -17.44)
TURN_POINT = (37.35, -4.4)  # over Andalusia, southern Spain


def flight_track():
    """Illustrative track: WAW -> great circle toward DKR -> U-turn over
    southern Spain -> return leg to WAW. Returns (outbound, turn, inbound,
    planned_remainder) lists of (lat, lon)."""
    # illustrative airway-style routing over Germany, France and eastern
    # Spain, with the turn placed over Andalusia (southern Spain)
    waypoints = [WARSAW, (49.0, 9.0), (43.2, 1.6), TURN_POINT]
    outbound = []
    for a, b in zip(waypoints, waypoints[1:]):
        seg = great_circle(a, b, 60)
        outbound += seg if not outbound else seg[1:]
    turn_pt = outbound[-1]
    remainder = great_circle(turn_pt, DAKAR, 120)
    planned = outbound
    idx = len(outbound) - 1
    # tight 180-degree loop to the right (west then north)
    hdg = bearing(planned[idx - 1], turn_pt)
    r = 0.55  # degrees
    # loop centre perpendicular (right side) of the heading
    rh = math.radians(hdg + 90)
    cos_lat = math.cos(math.radians(turn_pt[0]))
    cx = turn_pt[1] + r * math.sin(rh) / cos_lat
    cy = turn_pt[0] + r * math.cos(rh)
    start_ang = math.atan2(turn_pt[0] - cy, (turn_pt[1] - cx) * cos_lat)
    turn = []
    for i in range(1, 41):
        ang = start_ang - math.pi * i / 40  # clockwise sweep (right turn)
        turn.append((cy + r * math.sin(ang), cx + r * math.cos(ang) / cos_lat))
    inbound = great_circle(turn[-1], WARSAW, 300)
    return outbound, turn, inbound, remainder
