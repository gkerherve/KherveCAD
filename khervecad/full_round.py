"""SolidWorks' **Full Round Fillet** (2026-11-14, Exercise 6 of the
user's SolidWorks videos: "side face set 1, centre face, side face set
2"): the CENTRE face is replaced by a half round tangent to both SIDE
faces — its radius is half the distance between them, found by itself.

`pick` rows [x, y, z] (in the children's frame) are three points: side
face 1, the centre face, side face 2 — the order SolidWorks asks for.
One row = the centre face alone; none = the topmost flat face. With
fewer than three, the two sides are the faces standing either side of
the centre face that look opposite ways (the pair with the longest
shared edge).

How: in the frame (d across the sides, n out of the centre face, a along
it), the part loses a box between the side faces, from r below the
centre face up past it, along the centre face's length, MINUS the round
bar of radius r on the axis r below the face — a Manifold difference,
exact. Baked like the other kit wrappers: `kcad_full_round(pick=,
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

_DEFAULTS = {"pick": []}
#: segments round the half round's full circle
SEGMENTS = 128
#: how far the cutter reaches past the faces, so no face is coplanar
EPS = 1e-3


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _sides(tris, normals, region, n):
    """(normal, point) of the two faces either side of the region: the
    neighbours across its rim standing square to *n*, the opposite pair
    sharing the most rim length."""
    owner = {}
    for i, t in enumerate(tris):
        for k in range(3):
            owner.setdefault(frozenset((_key(t[k]), _key(t[(k + 1) % 3]))),
                             []).append(i)
    found = {}
    for i in region:
        t = tris[i]
        for k in range(3):
            a, b = t[k], t[(k + 1) % 3]
            for j in owner.get(frozenset((_key(a), _key(b))), ()):
                m = normals[j]
                if j in region or m is None or abs(_dot(m, n)) > 0.01:
                    continue
                key = tuple(round(x, 3) for x in m)
                f = found.setdefault(key, [m, tris[j][0], 0.0])
                f[2] += math.dist(a, b)
    best = None
    for key, (m, p, length) in found.items():
        back = tuple(round(-x, 3) for x in m)
        if back in found and length >= found[back][2]:
            score = length + found[back][2]
            if best is None or score > best[0]:
                best = (score, (m, p), (found[back][0], found[back][1]))
    return (best[1], best[2]) if best else None


def round_off(tris, picks):
    """*tris* with the centre face fully rounded, or None when the faces
    do not make a full round (then the part is left as it was)."""
    import manifold3d as m
    from . import csg
    from .dome import _top_face
    tris = [tuple(t[:3]) for t in tris]
    normals = [_normal(t) for t in tris]
    if not picks:
        top = _top_face(tris)
        if top is None:
            return None
        picks = [top]
    centre_pt = picks[1] if len(picks) >= 3 else picks[0]
    ic = _nearest(tris, centre_pt)
    if ic is None or normals[ic] is None:
        return None
    n = normals[ic]
    region = _coplanar_region(tris, normals, ic)
    if len(picks) >= 3:
        sides = []
        for p in (picks[0], picks[2]):
            i = _nearest(tris, p)
            if i is None or normals[i] is None:
                return None
            sides.append((normals[i], tris[i][0]))
    else:
        sides = _sides(tris, normals, region, n)
        if sides is None:
            return None
    (d, p1), (d2, p2) = sides
    if _dot(d, d2) > -0.999 or abs(_dot(d, n)) > 0.01:
        return None                         # not two opposite side faces
    hi, lo = _dot(d, p1), _dot(d, p2)
    if hi - lo < 1e-6:
        return None
    r = (hi - lo) / 2
    mid = (hi + lo) / 2
    a = _cross(d, n)
    pts = [p for i in region for p in tris[i]]
    amin = min(_dot(a, p) for p in pts)
    amax = max(_dot(a, p) for p in pts)
    h = _dot(n, tris[ic][0])
    # in the local frame x = d, y = n, z = a
    box = m.Manifold.cube([hi - lo + 2 * EPS, r + 2 * EPS,
                           amax - amin]).translate([lo - EPS, h - r,
                                                    amin])
    bar = m.Manifold.cylinder(amax - amin + 2 * EPS, r, r, SEGMENTS
                              ).translate([mid, h - r, amin - EPS])
    cutter = (box - bar).transform([[d[0], n[0], a[0], 0.0],
                                    [d[1], n[1], a[1], 0.0],
                                    [d[2], n[2], a[2], 0.0]])
    solid = csg.to_manifold([(t, None, False) for t in tris], {})
    if solid is None:
        return None
    return csg.to_triangles(solid - cutter)


def _compute(node, env):
    from . import csg
    tris = [tuple(t[:3]) for t in bakedkit.source_tris(node, env)]
    if not tris or not csg.available():
        return tris
    picks = [r[:3] for r in bakedkit.rows(node, env, "pick", 3)]
    out = round_off(tris, picks)
    return out if out else tris


def _check(node, env):
    picks = node.params.get("pick") or []
    if len(picks) not in (0, 1, 3):
        return ("Full round fillet: click three faces — side, centre, "
                "side — or the centre face alone")
    from . import csg
    if not csg.available():
        return "Full round fillet needs manifold3d"
    tris = [tuple(t[:3]) for t in bakedkit.source_tris(node, env)]
    rows = [r[:3] for r in bakedkit.rows(node, env, "pick", 3)]
    if tris and round_off(tris, rows) is None:
        return ("Full round fillet: the side faces must stand either "
                "side of the centre face, looking opposite ways")
    return None


KIT = bakedkit.make(
    "full_round", "Full Round Fillet", "mdi.rounded-corner", _DEFAULTS,
    [("pick", "Faces: side, centre, side (none = the top face)",
      "rows", ["X", "Y", "Z"], None)],
    _compute, check=_check, inexact_ok=True)
