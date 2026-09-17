"""Build ``khervecad/solar/earth_coast.json.gz`` from Natural Earth's
1:50m land, lakes and glaciated-areas GeoJSON (public domain):

    python -m khervecad.tools.earth_coast ne_50m_land.geojson \\
        ne_50m_lakes.geojson ne_50m_glaciated_areas.geojson

Outer rings only, Douglas-Peucker simplified to TOLERANCE degrees,
rings under MIN_AREA square degrees dropped, Antarctica's polar edge
clamped to CLAMP_LAT (the ring runs along -90, which the sphere folds
to one point), and every ring ear-clipped once here so the globe builds
without a two-second triangulation of Eurasia.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import gzip
import json
import math
import sys
from pathlib import Path

TOLERANCE = 0.1
MIN_AREA = 0.04
CLAMP_LAT = -89.0
OUT = Path(__file__).resolve().parents[1] / "solar" / "earth_coast.json.gz"


def rings(path):
    d = json.load(open(path))
    for ft in d["features"]:
        g = ft["geometry"]
        polys = [g["coordinates"]] if g["type"] == "Polygon" \
            else g["coordinates"]
        for p in polys:
            yield p[0]


def simplify(pts, tol):
    if len(pts) < 3:
        return pts
    a, b = pts[0], pts[-1]
    dmax, idx = 0.0, 0
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    length = math.hypot(bx - ax, by - ay)
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = (abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / length
             if length else math.hypot(px - ax, py - ay))
        if d > dmax:
            dmax, idx = d, i
    if dmax > tol:
        return simplify(pts[:idx + 1], tol)[:-1] + simplify(pts[idx:], tol)
    return [a, b]


def area(r):
    return abs(sum(r[i][0] * r[(i + 1) % len(r)][1]
                   - r[(i + 1) % len(r)][0] * r[i][1]
                   for i in range(len(r)))) / 2


def clean(ring, tol):
    ring = simplify(ring, tol)
    out = []
    for x, y in ring:
        x, y = round(x, 3), round(max(y, CLAMP_LAT), 3)
        if not out or [x, y] != out[-1]:
            out.append([x, y])
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def triangulate(ring):
    """Ear clipping in a plane where longitude is scaled by the cosine
    of the ring's mean latitude, so ears are well shaped up north."""
    from khervecad import mesh
    m = max(math.cos(math.radians(sum(y for _x, y in ring) / len(ring))),
            0.05)
    pts = [(x * m, y) for x, y in ring]
    index = {p: i for i, p in enumerate(pts)}
    # the clipper's last ear is never checked: a clockwise or flat one
    # would run an edge the same way as its neighbour
    return [[index[a], index[b], index[c]] for a, b, c in
            mesh.triangulate(pts)
            if (b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0]) > 1e-9]


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    out = {"source": "Natural Earth 1:50m (public domain): land, lakes "
                     "and glaciated areas, outer rings simplified to "
                     f"{TOLERANCE} degrees, triangulated",
           "tolerance": TOLERANCE}
    for key, path in zip(("land", "lakes", "ice"), argv):
        polys, seen = [], set()
        for ring in rings(path):
            if area(ring) < MIN_AREA:
                continue
            ring = clean(ring, TOLERANCE)
            sig = (len(ring), tuple(ring[0]), tuple(ring[-1]))
            if len(ring) < 3 or sig in seen:     # Lake Volta comes twice
                continue
            seen.add(sig)
            polys.append({"ring": ring, "tris": triangulate(ring)})
        out[key] = polys
        print(key, len(polys), "rings,", sum(len(p["ring"]) for p in polys),
              "vertices,", sum(len(p["tris"]) for p in polys), "triangles")
    with gzip.open(OUT, "wt") as f:
        json.dump(out, f, separators=(",", ":"))
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main(sys.argv[1:])
