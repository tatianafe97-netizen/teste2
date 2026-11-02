#!/usr/bin/env python3
"""Build the compact `data/geodata.json` used by the funding-map and radar scenes.

Run once (the output is committed, so the main pipeline works offline):

    .venv/bin/pip install shapely
    .venv/bin/python tools/build_geodata.py

Source: Natural Earth 1:10m Admin-0 countries, *Ukraine point-of-view* edition
(public domain). The Ukraine POV file draws Crimea as part of Ukraine, in line
with internationally recognised borders.
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

try:
    from shapely.geometry import shape, mapping, box
except ImportError:  # pragma: no cover
    sys.exit("shapely is required for this one-off tool: pip install shapely")

SRC_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_0_countries_ukr.geojson"
)
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "geodata.json"
CACHE = ROOT / "build" / "ne_10m_admin_0_countries_ukr.geojson"

# Regional detail box for the Ukraine radar scope (lon/lat).
REGION_BOX = (14.0, 40.0, 46.0, 57.0)


def rings(geom, nd: int = 2) -> list[list[list[float]]]:
    """Exterior rings of a (Multi)Polygon as rounded [lon, lat] lists."""
    out = []
    gj = mapping(geom)
    polys = gj["coordinates"] if gj["type"] == "MultiPolygon" else [gj["coordinates"]]
    for poly in polys:
        ring = poly[0]
        if len(ring) < 4:
            continue
        out.append([[round(x, nd), round(y, nd)] for x, y in ring])
    return out


def main() -> None:
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    if not CACHE.exists():
        print(f"Downloading {SRC_URL}")
        urllib.request.urlretrieve(SRC_URL, CACHE)
    data = json.loads(CACHE.read_text())

    world: dict[str, list] = {}
    region: dict[str, list] = {}
    clip = box(*REGION_BOX)
    for ft in data["features"]:
        code = ft["properties"]["ADM0_A3"]
        geom = shape(ft["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        coarse = geom.simplify(0.12, preserve_topology=True)
        if coarse.area > 0.05:  # drop tiny islands for the globe view
            r = rings(coarse, 1)
            if r:
                world[code] = r
        if geom.intersects(clip):
            fine = geom.intersection(clip).simplify(0.025, preserve_topology=True)
            if not fine.is_empty and fine.geom_type in ("Polygon", "MultiPolygon"):
                r = rings(fine)
                if r:
                    region[code] = r

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Natural Earth 1:10m Admin-0 countries (Ukraine POV), public domain",
        "world": world,
        "region": region,
    }, separators=(",", ":")))
    print(f"Wrote {OUT} ({OUT.stat().st_size / 1024:.0f} KB, "
          f"{len(world)} world / {len(region)} regional shapes)")


if __name__ == "__main__":
    main()
