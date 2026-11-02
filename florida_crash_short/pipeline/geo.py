"""Natural Earth (public domain) coastlines + state borders, clipped to the
Gulf of Mexico / Florida / Bahamas region and cached in data/region.json."""
import json
import os
import ssl
import urllib.request

from . import config as C
from .util import log

BBOX = (-101.0, 18.5, -72.0, 36.0)  # lon_min, lat_min, lon_max, lat_max
SOURCES = {
    "land": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_land.geojson",
    "admin1": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_1_states_provinces_lakes.geojson",
}
REGION = C.DATA / "region.json"


def _fetch(url):
    ctx = ssl.create_default_context()
    extra = os.environ.get("SSL_CERT_FILE")
    if extra and os.path.exists(extra):
        ctx.load_verify_locations(extra)
    with urllib.request.urlopen(url, context=ctx, timeout=60) as r:
        return json.loads(r.read())


def _rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    if geom["type"] == "MultiPolygon":
        return [p[0] for p in geom["coordinates"]]
    return []


def _in_bbox(ring):
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return not (max(xs) < BBOX[0] or min(xs) > BBOX[2] or max(ys) < BBOX[1] or min(ys) > BBOX[3])


def _round(ring):
    return [[round(x, 3), round(y, 3)] for x, y in ring]


def load_region():
    if REGION.exists():
        return json.loads(REGION.read_text())
    log("  fetching Natural Earth 1:50m coastline + state data (one-time)")
    C.DATA.mkdir(exist_ok=True)
    land = _fetch(SOURCES["land"])
    admin = _fetch(SOURCES["admin1"])
    out = {"land": [], "states": []}
    for f in land["features"]:
        out["land"] += [_round(r) for r in _rings(f["geometry"]) if _in_bbox(r)]
    for f in admin["features"]:
        if f["properties"].get("adm0_a3") not in ("USA", "MEX", "CUB", "BHS"):
            continue
        out["states"] += [_round(r) for r in _rings(f["geometry"]) if _in_bbox(r)]
    REGION.write_text(json.dumps(out, separators=(",", ":")))
    return out
