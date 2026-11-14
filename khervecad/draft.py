"""SolidWorks' **Draft** (2026-11-14, the user, from the video's Features
tab: "the other icons which are not available on KCAD ... I don't think
we have draft").

A draft tilts a part's SIDE faces (those standing along the pull
direction, +Z in the part's frame) by `angle` degrees about a NEUTRAL
plane — the bottom of the part (it narrows going up, the usual moulding
draft) or its top — so the part comes out of a mould. `faces` rows
[x, y, z] name the faces to draft (a point on each, in the children's
frame; each grown over its coplanar neighbours); none = every side face.

How: each side face's plane moves by its height above the neutral plane
× tan(angle); a vertex lying on several faces is solved so it stays on
ALL of them (least squares over their horizontal normals — two walls of
a box meet in the right corner, a cylinder's facets move radially), a
side face not drafted holds its vertices to itself (constraint Δ·n = 0),
and nothing moves in z, so caps stay flat and the solid stays closed.
Baked like the other kit wrappers: `kcad_draft(angle=, neutral=,
faces=, points=, faces_=) { children }` draws the drafted polyhedron in
OpenSCAD too.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math

from . import bakedkit

#: a face is a SIDE face when its normal's z is under this (steeper than
#: about 72° from flat)
SIDE_NZ = 0.3
MAX_ANGLE = 45.0
_DEFAULTS = {"angle": 3.0, "neutral": "bottom", "pick": []}


def _key(p):
    return (round(p[0], 6), round(p[1], 6), round(p[2], 6))


def _normal(t):
    a, b, c = t[:3]
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
         u[0] * v[1] - u[1] * v[0]]
    m = math.sqrt(sum(x * x for x in n))
    return [x / m for x in n] if m > 1e-12 else None


def _coplanar_region(tris, normals, seed_i):
    """Indices of the triangles coplanar with *seed_i* and joined to it
    through shared vertices."""
    n0 = normals[seed_i]
    a0 = tris[seed_i][0]
    d0 = sum(n0[k] * a0[k] for k in range(3))
    cand = [i for i, n in enumerate(normals) if n is not None and
            sum(n[k] * n0[k] for k in range(3)) > 0.9999 and
            abs(sum(n[k] * tris[i][0][k] for k in range(3)) - d0) < 1e-4]
    keys = {i: {_key(p) for p in tris[i][:3]} for i in cand}
    region, frontier = {seed_i}, [seed_i]
    while frontier:
        i = frontier.pop()
        for j in cand:
            if j not in region and keys[i] & keys[j]:
                region.add(j)
                frontier.append(j)
    return region


def _nearest(tris, pt):
    best, bi = None, None
    for i, t in enumerate(tris):
        c = [sum(p[k] for p in t[:3]) / 3 for k in range(3)]
        d = sum((c[k] - pt[k]) ** 2 for k in range(3))
        if best is None or d < best:
            best, bi = d, i
    return bi


def draft_tris(tris, angle, neutral="bottom", picks=()):
    """*tris* (CCW, outward) with their side faces drafted *angle*°."""
    if not tris or abs(angle) < 1e-9:
        return list(tris)
    normals = [_normal(t) for t in tris]
    side = {i for i, n in enumerate(normals)
            if n is not None and abs(n[2]) < SIDE_NZ}
    if picks:
        chosen = set()
        for pt in picks:
            i = _nearest(tris, pt)
            if i is not None and i in side:
                chosen |= _coplanar_region(tris, normals, i)
        drafted = chosen & side
    else:
        drafted = side
    if not drafted:
        return list(tris)
    zs = [p[2] for t in tris for p in t[:3]]
    z0 = min(zs) if neutral != "top" else max(zs)
    sign = 1.0 if neutral != "top" else -1.0
    tan = math.tan(math.radians(angle))
    # per vertex: the horizontal normals of the side faces it lies on,
    # each with the offset it must move by (0 for an undrafted side)
    cons = {}
    for i in side:
        n = normals[i]
        h = math.hypot(n[0], n[1])
        if h < 1e-9:
            continue
        nx, ny = n[0] / h, n[1] / h
        for p in tris[i][:3]:
            lst = cons.setdefault(_key(p), [])
            if not any(abs(nx * a + ny * b - 1) < 1e-6 for a, b, _d in lst):
                lst.append((nx, ny, i in drafted))
    moved = {}
    for key, lst in cons.items():
        if not any(dr for *_n, dr in lst):
            continue
        d = -sign * (key[2] - z0) * tan        # inward going away
        # least squares: Σ n nᵀ Δ = Σ n · target
        a11 = a12 = a22 = b1 = b2 = 0.0
        for nx, ny, dr in lst:
            t = d if dr else 0.0
            a11 += nx * nx
            a12 += nx * ny
            a22 += ny * ny
            b1 += nx * t
            b2 += ny * t
        det = a11 * a22 - a12 * a12
        if abs(det) > 1e-9:
            dx = (b1 * a22 - b2 * a12) / det
            dy = (a11 * b2 - a12 * b1) / det
        else:                                  # one direction only
            k = a11 + a22
            dx, dy = (b1 / k, b2 / k) if k > 1e-12 else (0.0, 0.0)
        moved[key] = (key[0] + dx, key[1] + dy, key[2])
    out = []
    for t in tris:
        out.append(tuple(moved.get(_key(p), tuple(p)) for p in t[:3]))
    return out


def _compute(node, env):
    tris = [t[:3] for t in bakedkit.source_tris(node, env)]
    angle = bakedkit.num(node, env, "angle", 3.0)
    neutral = str(node.params.get("neutral", "bottom"))
    picks = [r[:3] for r in bakedkit.rows(node, env, "pick", 3)]
    return draft_tris(tris, angle, neutral, picks)


def _check(node, env):
    a = bakedkit.num(node, env, "angle", 3.0)
    if not -MAX_ANGLE <= a <= MAX_ANGLE:
        return "Draft: the angle must be between -%g and %g°" % (
            MAX_ANGLE, MAX_ANGLE)
    return None


KIT = bakedkit.make(
    "draft", "Draft", "mdi.trapezoid", _DEFAULTS,
    [("angle", "Draft angle (°)", "float", -MAX_ANGLE, MAX_ANGLE),
     ("neutral", "Neutral plane", "choice", None, None),
     ("pick", "Faces to draft (a point on each; none = every side)",
      "rows", ["X", "Y", "Z"], None)],
    _compute, choices={"neutral": ["bottom", "top"]}, check=_check,
    text=("neutral",))
