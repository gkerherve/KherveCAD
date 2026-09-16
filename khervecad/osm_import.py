"""OpenStreetMap -> City Builder spec (Qt-free).

`fetch(bbox)` asks the Overpass API for every road, building, tree and
wood in a latitude / longitude box; `to_spec(data, bbox)` turns the
answer into a City Builder spec in local millimetres (`geo.Projection`,
x east, y north, origin at the box centre):

- roads: every `highway` way clipped to the box (a polyline leaving and
  re-entering is split), kind from the highway class;
- buildings: the REAL outline — ``footprint`` in the building's own
  frame (turned by the ``rz`` of its minimum-area rectangle, so the
  plan, the pads and dragging keep working on ``x, y, w, d, rz``), a
  style guessed from the `building` / `amenity` tags, the height from
  ``height`` or ``building:levels`` and the roof from ``roof:shape``;
- trees: ``natural=tree`` nodes, and woods (``natural=wood``,
  ``landuse=forest``) planted on a jittered grid.

Nothing here downloads unless `fetch` is called, and it takes an
injectable ``opener`` for tests. Map data © OpenStreetMap contributors,
ODbL — the spec carries that attribution.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
import math
import random
import urllib.parse
import urllib.request

from .geo import urlopen as geo_urlopen

from .geo import projection_for

OVERPASS = "https://overpass-api.de/api/interpreter"
USER_AGENT = "KherveCAD map import (https://khervetools.com)"
ATTRIBUTION = "Map data © OpenStreetMap contributors (ODbL)"

ROAD_KIND = {"motorway": "avenue", "trunk": "avenue", "primary": "avenue",
             "secondary": "avenue", "tertiary": "street",
             "residential": "street", "unclassified": "street",
             "living_street": "street", "service": "lane", "track": "lane",
             "pedestrian": "path", "footway": "path", "path": "path",
             "cycleway": "path", "bridleway": "path", "steps": "path"}
ROAD_KIND.update({k + "_link": v for k, v in list(ROAD_KIND.items())})
ROOF = {"flat": "flat", "gabled": "gable", "hipped": "hip",
        "half-hipped": "hip", "pyramidal": "hip", "skillion": "gable",
        "gambrel": "gable", "mansard": "hip", "saltbox": "gable",
        "dome": "flat", "onion": "flat", "round": "gable"}
WOOD_SPACING = 12.0                  # m between planted wood trees
FLOOR_M = 3.0


class OsmError(RuntimeError):
    """The map could not be downloaded or read."""


def query(bbox):
    s, w, n, e = bbox
    b = f"({s:.7f},{w:.7f},{n:.7f},{e:.7f})"
    return ("[out:json][timeout:120];("
            f'way["highway"]{b};way["building"]{b};'
            f'way["natural"~"wood|water"]{b};way["landuse"~"forest"]{b};'
            f'node["natural"="tree"]{b};'
            f'relation["building"]{b};'
            ");out geom;")


def http_post(url, body, timeout=180):
    req = urllib.request.Request(url, data=body, headers={
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded"})
    with geo_urlopen(req, timeout) as r:
        return r.read()


def fetch(bbox, opener=http_post, url=OVERPASS):
    body = urllib.parse.urlencode({"data": query(bbox)}).encode()
    try:
        return json.loads(opener(url, body).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise OsmError(f"The OpenStreetMap download failed: {exc}")


# ----------------------------------------------------------- geometry
def _area(poly):
    return sum(poly[k][0] * poly[(k + 1) % len(poly)][1]
               - poly[(k + 1) % len(poly)][0] * poly[k][1]
               for k in range(len(poly))) / 2.0


def _clean(poly):
    """Drop the closing repeat and near-duplicate points; counter-
    clockwise."""
    out = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 50:
            out.append(p)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0],
                                   out[0][1] - out[-1][1]) <= 50:
        out.pop()
    if len(out) >= 3 and _area(out) < 0:
        out.reverse()
    return out


def min_rect(poly):
    """(cx, cy, w, d, angle_deg) of the minimum-area rectangle, w >= d,
    angle the direction of w."""
    best = None
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        a = math.atan2(y2 - y1, x2 - x1)
        c, s = math.cos(a), math.sin(a)
        u = [x * c + y * s for x, y in poly]
        v = [-x * s + y * c for x, y in poly]
        w, d = max(u) - min(u), max(v) - min(v)
        if w * d <= 0:
            continue
        if best is None or w * d < best[0]:
            cu, cv = (max(u) + min(u)) / 2, (max(v) + min(v)) / 2
            best = (w * d, cu * c - cv * s, cu * s + cv * c, w, d,
                    math.degrees(a))
    if best is None:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2,
                max(max(xs) - min(xs), 1.0), max(max(ys) - min(ys), 1.0), 0.0)
    _, cx, cy, w, d, a = best
    if w < d:
        w, d, a = d, w, a + 90.0
    return cx, cy, w, d, a % 360.0


def _clip_segment(p, q, box):
    """Liang-Barsky: the part of p->q inside box, or None."""
    x0, y0, x1, y1 = box
    t0, t1 = 0.0, 1.0
    dx, dy = q[0] - p[0], q[1] - p[1]
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0),
                   (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return None
            continue
        t = qq / pp
        if pp < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return ((p[0] + t0 * dx, p[1] + t0 * dy), (p[0] + t1 * dx, p[1] + t1 * dy))


def clip_polyline(points, box):
    """The pieces of a polyline inside box."""
    pieces, cur = [], []
    for p, q in zip(points, points[1:]):
        seg = _clip_segment(p, q, box)
        if seg is None:
            if len(cur) > 1:
                pieces.append(cur)
            cur = []
            continue
        a, b = seg
        if cur and math.hypot(cur[-1][0] - a[0], cur[-1][1] - a[1]) < 1:
            cur.append(b)
        else:
            if len(cur) > 1:
                pieces.append(cur)
            cur = [a, b]
    if len(cur) > 1:
        pieces.append(cur)
    return pieces


# ---------------------------------------------------------------- tags
def _metres(text):
    if text is None:
        return None
    t = str(text).strip().lower().replace(",", ".")
    try:
        if t.endswith("ft") or t.endswith("'"):
            return float(t.rstrip("ft'").strip()) * 0.3048
        return float(t.split()[0].rstrip("m"))
    except (ValueError, IndexError):
        return None


def style_for(tags, area_m2):
    b = (tags.get("building") or "yes").lower()
    amenity = (tags.get("amenity") or "").lower()
    religion = (tags.get("religion") or "").lower()
    if b == "mosque" or (amenity == "place_of_worship"
                         and religion == "muslim"):
        return "mosque"
    if b in ("church", "chapel", "cathedral") or amenity == \
            "place_of_worship":
        return "church"
    if b in ("garage", "garages", "shed", "hut", "carport", "kiosk",
             "roof", "greenhouse"):
        return "shop"
    if b in ("retail", "commercial", "supermarket", "shop") or \
            tags.get("shop"):
        return "shop"
    if b in ("apartments", "office", "school", "hospital", "industrial",
             "warehouse", "hotel", "university", "public", "civic",
             "government", "dormitory"):
        return "block"
    if b == "terrace":
        return "terrace"
    if area_m2 < 25:
        return "shop"
    if area_m2 > 400:
        return "block"
    return "house"


def _building_levels(tags, style, area_m2):
    h = _metres(tags.get("height"))
    levels = tags.get("building:levels")
    try:
        levels = float(levels) if levels is not None else None
    except ValueError:
        levels = None
    if h is None and levels is not None:
        roof = float(tags.get("roof:levels") or 0)
        h = (levels + 0.5 * roof) * FLOOR_M
    if h is None:
        return None, ({"shop": 1, "block": 3, "church": 2}.get(style)
                      or (1 if area_m2 < 40 else 2))
    return h * 1000.0, max(1, round(h / FLOOR_M))


# ---------------------------------------------------------------- spec
def to_spec(data, bbox, seed=1, trees=True, woods=True):
    """The City Builder spec for an Overpass answer (see module doc)."""
    proj = projection_for(bbox)
    s, w, n, e = bbox
    x0, y0 = proj.to_local(s, w)
    x1, y1 = proj.to_local(n, e)
    box = (x0, y0, x1, y1)
    rng = random.Random(seed)

    def local(geometry):
        return [proj.to_local(p["lat"], p["lon"]) for p in geometry
                if p]

    roads, buildings, tree_list, woods_polys = [], [], [], []
    for el in data.get("elements") or []:
        tags = el.get("tags") or {}
        if el.get("type") == "node" and tags.get("natural") == "tree":
            if not trees:
                continue
            x, y = proj.to_local(el["lat"], el["lon"])
            if x0 <= x <= x1 and y0 <= y <= y1:
                t = dict(kind="oak", x=round(x), y=round(y))
                h = _metres(tags.get("height"))
                if h:
                    t["height"] = round(h * 1000)
                tree_list.append(t)
            continue
        geometry = el.get("geometry")
        if el.get("type") == "relation":
            outer = [m for m in el.get("members") or []
                     if m.get("role") == "outer" and m.get("geometry")]
            if not outer:
                continue
            geometry = outer[0]["geometry"]
        if not geometry:
            continue
        pts = local(geometry)
        if "highway" in tags:
            kind = ROAD_KIND.get(tags["highway"])
            if kind is None or tags.get("area") == "yes":
                continue
            for piece in clip_polyline(pts, box):
                roads.append(dict(kind=kind, name=tags.get("name", ""),
                                  points=[[round(x), round(y)]
                                          for x, y in piece]))
        elif "building" in tags:
            poly = _clean(pts)
            if len(poly) < 3:
                continue
            cx, cy, bw, bd, rz = min_rect(poly)
            if not (x0 <= cx <= x1 and y0 <= cy <= y1):
                continue
            area = abs(_area(poly)) / 1e6
            style = style_for(tags, area)
            height, floors = _building_levels(tags, style, area)
            a = math.radians(rz)
            c, sn = math.cos(a), math.sin(a)
            frame = [[round((x - cx) * c + (y - cy) * sn),
                      round(-(x - cx) * sn + (y - cy) * c)] for x, y in poly]
            b = dict(style=style, x=round(cx), y=round(cy), w=round(bw),
                     d=round(bd), rz=round(rz, 2), floors=floors,
                     footprint=frame, osm_id=el.get("id"))
            if height:
                b["height"] = round(height)
            roof = ROOF.get((tags.get("roof:shape") or "").lower())
            if roof:
                b["roof"] = roof
            elif style in ("house", "terrace") and area < 250:
                b["roof"] = "hip" if abs(bw - bd) < 3000 else "gable"
            if tags.get("name"):
                b["name"] = tags["name"]
            elif tags.get("addr:housenumber"):
                b["name"] = " ".join(v for v in (
                    tags.get("addr:housenumber"), tags.get("addr:street"))
                    if v)
            buildings.append(b)
        elif woods and (tags.get("natural") == "wood"
                        or tags.get("landuse") == "forest"):
            woods_polys.append(_clean(pts))
    if woods and trees:
        from .lidar import inside
        step = WOOD_SPACING * 1000.0
        for poly in woods_polys:
            if len(poly) < 3:
                continue
            xs, ys = [p[0] for p in poly], [p[1] for p in poly]
            gx = max(min(xs), x0)
            while gx < min(max(xs), x1):
                gy = max(min(ys), y0)
                while gy < min(max(ys), y1):
                    px = gx + rng.uniform(-0.35, 0.35) * step
                    py = gy + rng.uniform(-0.35, 0.35) * step
                    if inside(poly, px, py):
                        tree_list.append(dict(
                            kind=rng.choice(["oak", "oak", "birch", "maple",
                                             "lime"]),
                            x=round(px), y=round(py),
                            height=round(rng.uniform(9000, 17000))))
                    gy += step
                gx += step
    return dict(name="Map import", roads=roads, buildings=buildings,
                trees=tree_list, ground={"margin": 0},
                geo=dict(proj.as_dict(), bbox=list(bbox),
                         attribution=ATTRIBUTION))
