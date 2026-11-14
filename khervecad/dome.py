"""SolidWorks' **Dome** (2026-11-14, the user: the Features tab's tools
KherveCAD lacked — "the Wrap, the Dome").

A dome bulges a FLAT face out by `height` (or dents it in, `reverse`):
the face's triangles are refined, and each point inside the face rises
along the face's normal by height × sqrt(1 - (1 - s)²), s its distance
to the face's edge over the largest such distance — a quarter ellipse
across, so a round face becomes exactly half an ellipsoid. The face's
EDGE does not move, so the part stays one closed solid. `pick` rows
[x, y, z] are a point on each face to dome (in the children's frame,
found again on every rebuild); none = the topmost flat face.
Baked like the other kit wrappers: `kcad_dome(height=, reverse=, pick=,
points=, faces=) { children }`.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit
from .draft import _coplanar_region, _key, _nearest, _normal

#: refinement: edges longer than the face's size / this are split
STEPS = 28
#: rings of equal distance from the face's edge the points settle on
RINGS = 14
_DEFAULTS = {"height": 10.0, "reverse": False, "pick": []}


def _frame(n):
    """Two unit vectors spanning the plane of normal *n*."""
    a = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    u = [n[1] * a[2] - n[2] * a[1], n[2] * a[0] - n[0] * a[2],
         n[0] * a[1] - n[1] * a[0]]
    m = math.sqrt(sum(x * x for x in u))
    u = [x / m for x in u]
    v = [n[1] * u[2] - n[2] * u[1], n[2] * u[0] - n[0] * u[2],
         n[0] * u[1] - n[1] * u[0]]
    return u, v


def _seg_dist(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-18 else max(0.0, min(1.0, ((p[0] - a[0]) * dx +
                                                  (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _inside(p, tris2):
    for a, b, c in tris2:
        d1 = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        d2 = (c[0] - b[0]) * (p[1] - b[1]) - (c[1] - b[1]) * (p[0] - b[0])
        d3 = (a[0] - c[0]) * (p[1] - c[1]) - (a[1] - c[1]) * (p[0] - c[0])
        if (d1 >= -1e-9 and d2 >= -1e-9 and d3 >= -1e-9) or \
                (d1 <= 1e-9 and d2 <= 1e-9 and d3 <= 1e-9):
            return True
    return False


def _loops(segs):
    """Chain directed 2D segments (face on their left) into loops."""
    nxt = {}
    for a, b in segs:
        nxt.setdefault((round(a[0], 6), round(a[1], 6)), []).append(b)
    loops, used = [], set()
    for a, _b in segs:
        k = (round(a[0], 6), round(a[1], 6))
        if k in used:
            continue
        loop, cur = [], a
        while True:
            ck = (round(cur[0], 6), round(cur[1], 6))
            if ck in used or ck not in nxt:
                break
            used.add(ck)
            loop.append(tuple(cur))
            cur = nxt[ck][0]
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def _area(loop):
    return sum(loop[i][0] * loop[(i + 1) % len(loop)][1] -
               loop[(i + 1) % len(loop)][0] * loop[i][1]
               for i in range(len(loop))) / 2


def dome_face(tris, seed_pt, height):
    """*tris* with the flat face holding *seed_pt* domed by *height*.

    The face is rebuilt as BANDS between rings of equal distance from
    its edge (Manifold's offset, so any outline and its holes work),
    each band triangulated from its two rings' points only and every
    ring lifted to its own height — no point lies between two heights,
    so the rim rises evenly (moving a split fan's points round left
    teeth on a round face and folds on a square one). Ring 0 is the
    face's own edge, unchanged, so the part stays closed."""
    import manifold3d as m
    import numpy as np
    normals = [_normal(t) for t in tris]
    i0 = _nearest(tris, seed_pt)
    if i0 is None or normals[i0] is None:
        return list(tris)
    region = _coplanar_region(tris, normals, i0)
    n = normals[i0]
    o = tris[i0][0]
    u, v = _frame(n)

    def to2(p):
        d = [p[k] - o[k] for k in range(3)]
        return (sum(d[k] * u[k] for k in range(3)),
                sum(d[k] * v[k] for k in range(3)))

    count = {}
    for i in region:
        t = tris[i][:3]
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            k = frozenset((_key(a), _key(b)))
            count[k] = count.get(k, 0) + 1
    segs = []
    for i in region:
        t = tris[i][:3]
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            if count[frozenset((_key(a), _key(b)))] == 1:
                segs.append((to2(a), to2(b)))
    ring0 = _loops(segs)
    if not ring0:
        return list(tris)
    cs = m.CrossSection([np.array(lp, float) for lp in ring0],
                        m.FillRule.EvenOdd)
    lo, hi = 0.0, max(abs(_area(lp)) for lp in ring0) ** 0.5
    for _ in range(40):                    # the deepest inside point
        mid = (lo + hi) / 2
        if cs.offset(-mid, m.JoinType.Round, 2.0, 0).is_empty():
            hi = mid
        else:
            lo = mid
    far = lo
    if far <= 1e-9:
        return list(tris)
    seg_len = far / 8
    rings = [ring0]
    heights = [0.0]
    for k in range(1, RINGS + 1):
        frac = k / RINGS
        dk = far * (1 - math.sqrt(max(0.0, 1 - frac ** 2))) * 0.999 \
            if k < RINGS else far * 0.999
        dk = max(dk, far * 1e-3)
        off = cs.offset(-dk, m.JoinType.Round, 2.0,
                        max(16, int(2 * math.pi * far / seg_len)))
        loops = [[tuple(p) for p in lp] for lp in off.to_polygons()
                 if len(lp) >= 3]
        if not loops:
            break
        rings.append(loops)
        s_ = min(dk / far, 1.0)
        heights.append(height * math.sqrt(max(0.0, 1 - (1 - s_) ** 2)))

    def world(q, h):
        return tuple(o[i] + u[i] * q[0] + v[i] * q[1] + n[i] * h
                     for i in range(3))

    out = [t for j, t in enumerate(tris) if j not in region]
    def lift(q, h, level):
        if level == 0:                     # the face's own edge points
            k = (round(q[0], 6), round(q[1], 6))
            return _edge_point.get(k) or world(q, 0.0)
        return world(q, h)
    _edge_point = {}
    for i in region:
        for p3 in tris[i][:3]:
            q = to2(p3)
            _edge_point[(round(q[0], 6), round(q[1], 6))] = tuple(p3)

    def emit(polys, levels):
        flat = [p for lp in polys for p in lp]
        lev = [lv for lp, lv in zip(polys, levels) for _p in lp]
        if len(flat) < 3:
            return
        try:
            idx = m.triangulate([np.array(lp, float) for lp in polys])
        except Exception:
            return
        for a, b, c in idx:
            pa = lift(flat[a], heights[lev[a]], lev[a])
            pb = lift(flat[b], heights[lev[b]], lev[b])
            pc = lift(flat[c], heights[lev[c]], lev[c])
            tn = _normal((pa, pb, pc))
            if tn is not None and sum(tn[i] * n[i] for i in range(3)) < 0:
                pb, pc = pc, pb
            out.append((pa, pb, pc))
    # bands: ring k's loops (face on their left) and ring k+1's reversed
    for k in range(len(rings) - 1):
        polys = [list(lp) for lp in rings[k]] + \
            [list(reversed(lp)) for lp in rings[k + 1]]
        emit(polys, [k] * len(rings[k]) + [k + 1] * len(rings[k + 1]))
    # the cap inside the last ring
    last = len(rings) - 1
    emit([list(lp) for lp in rings[last]], [last] * len(rings[last]))
    return out


def _top_face(tris):
    """A point on the topmost upward flat face."""
    best = None
    for t in tris:
        n = _normal(t)
        if n is None or n[2] < 0.9999:
            continue
        z = t[0][2]
        if best is None or z > best[0]:
            best = (z, [sum(p[k] for p in t) / 3 for k in range(3)])
    return best[1] if best else None


def _compute(node, env):
    tris = [tuple(t[:3]) for t in bakedkit.source_tris(node, env)]
    h = bakedkit.num(node, env, "height", 10.0)
    if node.params.get("reverse"):
        h = -h
    picks = [r[:3] for r in bakedkit.rows(node, env, "pick", 3)]
    if not picks:
        top = _top_face(tris)
        picks = [top] if top else []
    for pt in picks:
        tris = dome_face(tris, pt, h)
    return tris


def _check(node, env):
    if bakedkit.num(node, env, "height", 10.0) <= 0:
        return "Dome: the height must be more than 0 (Reverse dents it in)"
    return None


KIT = bakedkit.make(
    "dome", "Dome", "mdi.circle-half-full", _DEFAULTS,
    [("height", "Height (mm)", "float", 0.0, 1e6),
     ("reverse", "Reverse (dent in)", "bool", None, None),
     ("pick", "Faces to dome (a point on each; none = the top face)",
      "rows", ["X", "Y", "Z"], None)],
    _compute, check=_check)
