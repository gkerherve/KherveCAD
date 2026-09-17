"""The Earth's land from real coastlines (Qt-free): Natural Earth's
1:50m land, lakes and glaciated areas (public domain, simplified to
0.1° and pre-triangulated by `khervecad.tools.earth_coast` into
``solar/earth_coast.json.gz``) stood on the globe as curved slabs.

Each ring's triangles are mapped onto the sphere and refined
(`deform.split_long_edges`, so no chord sags below the sphere's
facets), then classified per triangle — green, taiga, desert or ice
from the hand map in `solar_maps` plus latitude rules — and every
class becomes ONE closed polyhedron: its outer triangles, the same
triangles mirrored underneath, and walls along its boundary edges,
including where two classes meet. Lakes and ice fields are thinner
slabs on top of the land. A coarse level re-simplifies the rings
(`simplify`) and re-triangulates at build time for the orreries.

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
from functools import lru_cache
from pathlib import Path

from . import solar_maps as M
from .model import CadNode
from .solar_surface import band, col, point

DATA = Path(__file__).resolve().parent / "solar" / "earth_coast.json.gz"
ELEVATION = Path(__file__).resolve().parent / "solar" / "earth_elevation.bin.gz"
EARTH_RADIUS_M = 6_371_000.0
#: metres above which land reads as bare rock, then as snow
ROCK_ABOVE = 2200.0
SNOW_ABOVE = 4500.0
#: how many times taller than life the relief stands, by default:
#: Everest at 50x is 7 % of the radius, 2 mm on a 60 mm globe, and the
#: Tibetan plateau a clear step — a raised-relief globe's exaggeration;
#: true scale would be a coat of paint (the user asked for the landscape
#: to show in 3D)
RELIEF = 50.0

#: radii of the slabs, as fractions of the globe's: land from just over
#: the base sphere's facets to its relief, lakes and ice a little higher
LAND = (1.0032, 1.008)
LAKE = (1.006, 1.010)
ICE = (1.006, 1.012)
#: longest chord on the surface, as fractions of the radius: lowlands
#: may keep 0.08 r (4.6°) chords, ground that rises is refined to
#: 0.03 r (1.7°) so a range stands as a range, not one bump
MAX_CHORD = 0.08
RELIEF_CHORD = 0.03
COARSE_CHORD = 0.25
COARSE_RELIEF_CHORD = 0.12
SLAB_CHORD = 0.12                  # lakes and ice fields
#: an edge counts as rising ground when its ends differ by this many
#: metres, or its middle leaves the straight line by half of it — a
#: plateau or an ice sheet stays coarse, a range is refined
RELIEF_STEP = 200.0
#: an orrery's Earth is millimetres across: simplify the coastline to
#: 1.2°, drop anything under 6 square degrees and leave the relief off
#: — at that size it is invisible, and it cost 19k of the orrery's 76k
#: triangles, a quarter of every frame for one 10 mm globe
COARSE_TOLERANCE = 1.2
COARSE_MIN_AREA = 6.0

CLASS_COLOURS = {k: v[0] for k, v in M.EARTH_PALETTE.items()}
CLASS_COLOURS["r"] = "#8b7d6b"                # bare rock
LAKE_COLOUR = "#2f6fc4"


@lru_cache(maxsize=1)
def load() -> dict:
    with gzip.open(DATA, "rt") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def elevation_grid():
    """(width, height, int16 metres row-major from 90 N, 180 W)."""
    import struct
    from array import array
    with gzip.open(ELEVATION, "rb") as f:
        head = f.read(16)
        if head[:8] != b"KCADELEV":
            raise ValueError("not an elevation grid")
        width, height = struct.unpack("<II", head[8:])
        grid = array("h")
        grid.frombytes(f.read())
    if len(grid) != width * height:
        raise ValueError("elevation grid is truncated")
    return width, height, grid


def elevation(lat, lon) -> float:
    """Land height in metres at a point, bilinear; 0 at sea."""
    width, height, grid = elevation_grid()
    u = (lon + 180.0) / 360.0 * width - 0.5
    v = (90.0 - lat) / 180.0 * height - 0.5
    i, j = math.floor(u), math.floor(v)
    fu, fv = u - i, v - j
    j0, j1 = min(max(j, 0), height - 1), min(max(j + 1, 0), height - 1)
    i0, i1 = i % width, (i + 1) % width
    top = grid[j0 * width + i0] * (1 - fu) + grid[j0 * width + i1] * fu
    bottom = grid[j1 * width + i0] * (1 - fu) + grid[j1 * width + i1] * fu
    return top * (1 - fv) + bottom * fv


def simplify(ring, tol):
    """Douglas-Peucker on a closed ring (as a polyline from its first
    point round to itself)."""
    pts = [tuple(p) for p in ring] + [tuple(ring[0])]

    def rec(seg):
        if len(seg) < 3:
            return seg
        a, b = seg[0], seg[-1]
        dmax, idx = 0.0, 0
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        for i in range(1, len(seg) - 1):
            p = seg[i]
            d = (abs((b[0] - a[0]) * (a[1] - p[1])
                     - (a[0] - p[0]) * (b[1] - a[1])) / length
                 if length else math.hypot(p[0] - a[0], p[1] - a[1]))
            if d > dmax:
                dmax, idx = d, i
        if dmax > tol:
            return rec(seg[:idx + 1])[:-1] + rec(seg[idx:])
        return [a, b]
    out = rec(pts)[:-1]
    return [p for i, p in enumerate(out) if i == 0 or p != out[i - 1]]


def _area(ring):
    return abs(sum(ring[i][0] * ring[(i + 1) % len(ring)][1]
                   - ring[(i + 1) % len(ring)][0] * ring[i][1]
                   for i in range(len(ring)))) / 2


def _triangulate(ring):
    from . import mesh
    m = max(math.cos(math.radians(sum(y for _x, y in ring) / len(ring))),
            0.05)
    pts = [(x * m, y) for x, y in ring]
    index = {p: i for i, p in enumerate(pts)}
    return [(index[a], index[b], index[c]) for a, b, c in
            mesh.triangulate(pts)
            if (b[0] - a[0]) * (c[1] - a[1])
            - (b[1] - a[1]) * (c[0] - a[0]) > 1e-9]


def polygons(key: str, fine: bool):
    """[(ring, tris)] of *key* ("land", "lakes", "ice"): the shipped
    fine triangulation, or the rings re-simplified and re-triangulated
    for a coarse globe."""
    out = []
    for poly in load()[key]:
        if fine:
            out.append((poly["ring"], poly["tris"]))
            continue
        if _area(poly["ring"]) < COARSE_MIN_AREA:
            continue
        ring = simplify(poly["ring"], COARSE_TOLERANCE)
        if len(ring) >= 3:
            out.append((ring, _triangulate(ring)))
    return out


def classify(lat, lon, height=None) -> str:
    """The climate class at a point: snow or bare rock by *height*
    (metres), else the hand map's cell, the nearest land cell when the
    finer coastline reaches past it, and ice towards the poles whatever
    the map says."""
    if lat < -60:
        return "i"
    if height is not None:
        if height > SNOW_ABOVE:
            return "i"
        if height > ROCK_ABOVE:
            return "r"
    rows = M.EARTH
    r = min(max(int((90 - lat) // 5), 0), len(rows) - 1)
    c = int((lon + 180) // 5) % len(rows[0])
    ch = rows[r][c]
    if ch == ".":
        for radius in (1, 2, 3):
            for dr in range(-radius, radius + 1):
                for dc in range(-radius, radius + 1):
                    rr = r + dr
                    if 0 <= rr < len(rows):
                        cc = (c + dc) % len(rows[0])
                        if rows[rr][cc] != ".":
                            return rows[rr][cc]
        return "t" if abs(lat) > 55 else "g"
    return ch


def _flip_delaunay(pts, tris, passes=20):
    """Edge flips towards a Delaunay triangulation of *tris* (index
    triples into planar *pts*, counter-clockwise): the ear clipper
    leaves fans of slivers across a continent, which shade as streaks
    and split into sawteeth; flipping the interior edges (never the
    boundary) gives well-shaped triangles from the same vertices."""
    tris = [tuple(t) for t in tris]

    def ccw(a, b, c):
        return ((pts[b][0] - pts[a][0]) * (pts[c][1] - pts[a][1])
                - (pts[b][1] - pts[a][1]) * (pts[c][0] - pts[a][0]))

    def in_circle(a, b, c, d):
        ax, ay = pts[a][0] - pts[d][0], pts[a][1] - pts[d][1]
        bx, by = pts[b][0] - pts[d][0], pts[b][1] - pts[d][1]
        cx, cy = pts[c][0] - pts[d][0], pts[c][1] - pts[d][1]
        return ((ax * ax + ay * ay) * (bx * cy - cx * by)
                - (bx * bx + by * by) * (ax * cy - cx * ay)
                + (cx * cx + cy * cy) * (ax * by - bx * ay)) > 1e-12
    for _ in range(passes):
        owner = {}
        for n, (a, b, c) in enumerate(tris):
            owner[(a, b)] = n
            owner[(b, c)] = n
            owner[(c, a)] = n
        flipped = 0
        done = set()
        for (a, b), n in list(owner.items()):
            m = owner.get((b, a))
            if m is None or n in done or m in done:
                continue
            t1, t2 = tris[n], tris[m]
            c = next(v for v in t1 if v not in (a, b))
            d = next(v for v in t2 if v not in (a, b))
            if not in_circle(a, b, c, d):
                continue
            if ccw(d, c, a) <= 1e-12 or ccw(c, d, b) <= 1e-12:
                continue                      # the flip would fold
            tris[n] = (c, d, b)
            tris[m] = (d, c, a)
            done.update((n, m))
            flipped += 1
        if not flipped:
            break
    return tris


def _refine(pts, tris, r, chord, fine_chord, rising, passes=1):
    """Split long edges at their midpoints, conforming (the decision is
    the edge's, both triangles make it, as in deform.split_long_edges),
    in the (lon, lat) plane with chord lengths measured on the sphere:
    every edge down to *chord*, and to *fine_chord* where *rising*
    (metres at a point) says the ground climbs. Returns the new tris;
    *pts* grows with the midpoints. One pass at a time, so the caller
    can flip in between: bisecting a sliver only breeds slivers, a
    flip after each pass turns them into fair triangles."""
    tris = [tuple(t) for t in tris]

    def length(a, b):
        (x0, y0), (x1, y1) = pts[a], pts[b]
        mid = math.radians((y0 + y1) / 2)
        return r * math.hypot(math.radians(x1 - x0) * math.cos(mid),
                              math.radians(y1 - y0))

    def long(a, b):
        ln = length(a, b)
        if ln > chord:
            return True
        if ln <= fine_chord:
            return False
        (x0, y0), (x1, y1) = pts[a], pts[b]
        h0, h1 = rising(y0, x0), rising(y1, x1)
        hm = rising((y0 + y1) / 2, (x0 + x1) / 2)
        return (abs(h0 - h1) > RELIEF_STEP
                or abs(hm - (h0 + h1) / 2) > RELIEF_STEP / 2)
    for _ in range(passes):
        mids = {}

        def mid(a, b):
            key = (a, b) if a < b else (b, a)
            m = mids.get(key)
            if m is None:
                m = mids[key] = len(pts)
                pts.append(((pts[a][0] + pts[b][0]) / 2,
                            (pts[a][1] + pts[b][1]) / 2))
            return m
        out, changed = [], False
        for a, b, c in tris:
            la, lb, lc = long(a, b), long(b, c), long(c, a)
            count = la + lb + lc
            if not count:
                out.append((a, b, c))
                continue
            changed = True
            if count == 3:
                ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
                out += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
            elif count == 1:
                if lb:
                    a, b, c = b, c, a
                elif lc:
                    a, b, c = c, a, b
                ab = mid(a, b)
                out += [(a, ab, c), (ab, b, c)]
            else:
                if not la:
                    a, b, c = b, c, a
                elif not lb:
                    a, b, c = c, a, b
                ab, bc = mid(a, b), mid(b, c)
                out += [(b, bc, ab), (a, ab, bc), (a, bc, c)]
        tris = out
        if not changed:
            break
    return tris


def _surface(polys, r, chord, fine_chord, rising=None):
    """Triangles on the sphere of radius *r* covering *polys*
    [(ring, tris)]: each ring's triangulation flipped towards Delaunay,
    refined, then mapped."""
    out = []
    for ring, tris in polys:
        m = max(math.cos(math.radians(sum(y for _x, y in ring) / len(ring))),
                0.05)
        pts = [(x, y) for x, y in ring]
        plane = [(x * m, y) for x, y in ring]
        tris = _flip_delaunay(plane, tris)
        climb = rising or (lambda _lat, _lon: 0.0)
        for _ in range(16):
            before = len(tris)
            tris = _refine(pts, tris, r, chord, fine_chord, climb)
            if len(tris) == before:
                break
            plane.extend((x * m, y) for x, y in pts[len(plane):])
            tris = _flip_delaunay(plane, tris, passes=4)
        sphere = [point(r, y, x) for x, y in pts]
        out.extend((sphere[a], sphere[b], sphere[c]) for a, b, c in tris)
    return out


def _split_pinches(tris, points, orig):
    """Make the outer surface a 2-manifold with boundary: a vertex whose
    incident triangles form two fans that touch only at it (two islands
    of one class meeting at a point, a ring touching itself) is
    duplicated for every fan but the first, so the walls raised along
    the boundary never share a vertical edge twice."""
    incident = {}
    for n, tri in enumerate(tris):
        for v in tri:
            incident.setdefault(v, []).append(n)
    for v, owners in list(incident.items()):
        if len(owners) < 2:
            continue
        parent = {n: n for n in owners}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        by_other = {}
        for n in owners:
            for w in tris[n]:
                if w != v:
                    by_other.setdefault(w, []).append(n)
        for group in by_other.values():
            for n in group[1:]:
                parent[find(n)] = find(group[0])
        fans = {}
        for n in owners:
            fans.setdefault(find(n), []).append(n)
        for fan in list(fans.values())[1:]:
            copy = len(points)
            points.append(list(points[v]))
            orig.append(orig[v])
            for n in fan:
                tris[n] = tuple(copy if x == v else x for x in tris[n])


def _shell(tris, r_out, r_in, lift=None):
    """One closed polyhedron (OpenSCAD winding) from outer triangles
    on the sphere of radius *r_out* (counter-clockwise from outside):
    the same triangles at *r_in* underneath, walls along the boundary.
    *lift(point)* adds relief to a vertex's radius, both surfaces, so a
    slab on a plateau rides up with it."""
    index = {}
    points = []
    orig = []                  # the sphere point each index came from

    def vid(p, radius):
        key = (round(p[0], 6), round(p[1], 6), round(p[2], 6))
        i = index.get(key)
        if i is None:
            i = index[key] = len(points)
            r = radius + (lift(p) if lift else 0.0)
            scale = r / math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2)
            points.append([round(p[0] * scale, 4), round(p[1] * scale, 4),
                           round(p[2] * scale, 4)])
            orig.append(p)
        return i
    outer = []
    for a, b, c in tris:
        o = (vid(a, r_out), vid(b, r_out), vid(c, r_out))
        if len(set(o)) == 3:              # a seam folds some flat
            outer.append(o)
    _split_pinches(outer, points, orig)
    inner = {}

    def iv(o):
        i = inner.get(o)
        if i is None:
            p = orig[o]
            rr = r_in + (lift(p) if lift else 0.0)
            scale = rr / math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2)
            i = inner[o] = len(points)
            points.append([round(p[0] * scale, 4), round(p[1] * scale, 4),
                           round(p[2] * scale, 4)])
            orig.append(p)
        return i
    faces = []
    edges = set()
    for o in outer:
        faces.append([o[0], o[2], o[1]])          # clockwise from outside
        faces.append([iv(o[0]), iv(o[1]), iv(o[2])])       # faces in
        edges.update([(o[0], o[1]), (o[1], o[2]), (o[2], o[0])])
    for u, v in edges:
        if (v, u) in edges:
            continue                              # an inner edge
        faces.append([u, v, iv(v)])
        faces.append([u, iv(v), iv(u)])
    return points, faces


def land_nodes(r, fine=True, relief=RELIEF) -> list:
    """The land as one polyhedron per climate class — the surface
    lifted by *relief* times the true elevation, so the ranges stand
    up — then the lakes, the ice fields and the south polar cap that
    closes Antarctica's clamped ring."""
    k = relief * r / EARTH_RADIUS_M

    def lift(p):
        lat = math.degrees(math.atan2(p[2], math.hypot(p[0], p[1])))
        lon = math.degrees(math.atan2(p[1], p[0]))
        return k * elevation(lat, lon)
    chord = (MAX_CHORD if fine else COARSE_CHORD) * r
    fine_chord = (RELIEF_CHORD if fine else COARSE_RELIEF_CHORD) * r
    tris = _surface(polygons("land", fine), r, chord, fine_chord,
                    elevation if relief else None)
    by_class = {}
    for tri in tris:
        cx = [(tri[0][i] + tri[1][i] + tri[2][i]) / 3 for i in range(3)]
        lat = math.degrees(math.atan2(cx[2], math.hypot(cx[0], cx[1])))
        lon = math.degrees(math.atan2(cx[1], cx[0]))
        by_class.setdefault(classify(lat, lon, elevation(lat, lon)),
                            []).append(tri)
    nodes = []
    for ch in ("g", "t", "d", "r", "i"):
        if ch not in by_class:
            continue
        points, faces = _shell(by_class[ch], r * LAND[1], r * LAND[0], lift)
        nodes.append(col(f"Land {ch}", CLASS_COLOURS[ch], CadNode(
            "polyhedron", f"Land {ch}", dict(points=points, faces=faces))))
    if fine:
        for key, name, colour, (lo, hi) in (
                ("lakes", "Lakes", LAKE_COLOUR, LAKE),
                ("ice", "Ice fields", CLASS_COLOURS["i"], ICE)):
            tris = _surface(polygons(key, True), r, SLAB_CHORD * r,
                            SLAB_CHORD * r)
            points, faces = _shell(tris, r * hi, r * lo, lift)
            nodes.append(col(name, colour, CadNode(
                "polyhedron", name, dict(points=points, faces=faces))))
    nodes.append(band("South polar cap", r, -90.0, -88.5,
                      CLASS_COLOURS["i"], lift=LAND[1]))
    return nodes
